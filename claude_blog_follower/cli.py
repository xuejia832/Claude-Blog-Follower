"""CLI commands for Claude Blog Follower."""

import argparse
import sys
from datetime import datetime, timedelta

from rich.console import Console
from rich.progress import Progress
from rich.table import Table

from . import config
from .analyzer import analyze_article, generate_timeline_analysis
from .emailer import send_weekly_digest
from .report import generate_report, save_report
from .scraper import fetch_all_articles
from .storage import (
    get_all_articles,
    get_analyzed_articles,
    get_analyzed_count,
    get_article_count,
    get_articles_since,
    get_existing_urls,
    get_unanalyzed_articles,
    init_db,
    save_analysis,
    save_article,
)

console = Console()


def cmd_fetch(args):
    """Fetch articles from Anthropic."""
    init_db()

    if args.all:
        console.print("[bold blue]Fetching all articles from Anthropic sitemap...[/]")
        existing = get_existing_urls()
        console.print(f"  Already in database: {len(existing)}")

        with Progress() as progress:
            task = progress.add_task("Fetching articles...", total=None)

            def on_progress(current, total):
                progress.update(task, total=total, completed=current,
                                description=f"Fetching {current}/{total}...")

            articles = fetch_all_articles(existing_urls=existing,
                                          progress_callback=on_progress)

        new_count = 0
        for article in articles:
            saved = save_article(**article)
            if saved:
                new_count += 1

        console.print(f"\n[green]Done! {new_count} new articles saved.[/]")
    else:
        # --new: only fetch new articles
        console.print("[bold blue]Checking for new articles...[/]")
        existing = get_existing_urls()

        articles = fetch_all_articles(existing_urls=existing)
        new_count = 0
        for article in articles:
            saved = save_article(**article)
            if saved:
                new_count += 1

        if new_count > 0:
            console.print(f"[green]{new_count} new articles found and saved![/]")
        else:
            console.print("[dim]No new articles found.[/]")

    total = get_article_count()
    console.print(f"[bold]Total articles in database: {total}[/]")


def cmd_analyze(args):
    """Analyze articles using Claude API."""
    init_db()

    articles = get_unanalyzed_articles()
    if not articles:
        console.print("[dim]All articles have been analyzed.[/]")
        return

    count = len(articles)
    if args.limit and args.limit < count:
        articles = articles[:args.limit]
        count = len(articles)

    console.print(f"[bold blue]Analyzing {count} articles with Claude API...[/]")

    with Progress() as progress:
        task = progress.add_task("Analyzing...", total=count)

        for i, article in enumerate(articles):
            try:
                result = analyze_article(
                    title=article["title"],
                    date=article["published_date"],
                    content=article["content"],
                )
                save_analysis(
                    article_id=article["id"],
                    summary=result["summary"],
                    key_tech=result["key_tech"],
                    key_viewpoints=result["key_viewpoints"],
                )
            except Exception as e:
                console.print(f"  [red]Error analyzing '{article['title'][:40]}': {e}[/]")

            progress.update(task, completed=i + 1)

    console.print(f"[green]Done! {get_analyzed_count()}/{get_article_count()} articles analyzed.[/]")


def cmd_report(args):
    """Generate HTML analysis report."""
    init_db()

    articles = get_all_articles()
    if not articles:
        console.print("[yellow]No articles found. Run 'fetch --all' first.[/]")
        return

    console.print(f"[bold blue]Generating report from {len(articles)} articles...[/]")

    # Generate timeline analysis if we have analyzed articles
    timeline_analysis = ""
    analyzed = get_analyzed_articles()
    if analyzed:
        console.print("  Generating timeline analysis with Claude API...")
        try:
            article_data = [
                {
                    "title": a["title"],
                    "published_date": a["published_date"],
                    "summary": a["summary"],
                }
                for a in analyzed
            ]
            timeline_analysis = generate_timeline_analysis(article_data)
        except Exception as e:
            console.print(f"  [red]Timeline analysis failed: {e}[/]")

    html = generate_report(articles, timeline_analysis)
    path = save_report(html)

    console.print(f"[green]Report saved to: {path}[/]")
    console.print("  Open it in your browser to view.")


def cmd_weekly(args):
    """Run weekly workflow: fetch new → analyze → email digest."""
    init_db()

    # Step 1: Fetch new articles
    console.print("[bold blue]Step 1: Checking for new articles...[/]")
    existing = get_existing_urls()
    before_count = len(existing)
    fetch_start = datetime.now().isoformat()

    articles = fetch_all_articles(existing_urls=existing)
    new_count = 0
    for article in articles:
        saved = save_article(**article)
        if saved:
            new_count += 1

    if new_count == 0:
        console.print("[dim]No new articles this week. Skipping email.[/]")
        return

    console.print(f"  [green]{new_count} new articles found.[/]")

    # Step 2: Analyze new articles
    console.print("[bold blue]Step 2: Analyzing new articles...[/]")
    unanalyzed = get_unanalyzed_articles()
    for article in unanalyzed:
        try:
            result = analyze_article(
                title=article["title"],
                date=article["published_date"],
                content=article["content"],
            )
            save_analysis(
                article_id=article["id"],
                summary=result["summary"],
                key_tech=result["key_tech"],
                key_viewpoints=result["key_viewpoints"],
            )
        except Exception as e:
            console.print(f"  [red]Error: {e}[/]")

    # Step 3: Send email
    console.print("[bold blue]Step 3: Sending weekly digest email...[/]")
    new_articles = get_articles_since(fetch_start)
    try:
        sent = send_weekly_digest(list(new_articles))
        if sent:
            console.print(f"[green]Weekly digest sent to {config.EMAIL_TO}![/]")
        else:
            console.print("[dim]No articles to send.[/]")
    except Exception as e:
        console.print(f"[red]Email failed: {e}[/]")
        console.print("  Check your SMTP settings in .env")


def cmd_list(args):
    """List articles in database."""
    init_db()

    articles = get_all_articles(limit=args.count)
    if not articles:
        console.print("[yellow]No articles found. Run 'fetch --all' first.[/]")
        return

    table = Table(title="Tracked Articles")
    table.add_column("ID", style="dim", width=4)
    table.add_column("Date", style="cyan", width=14)
    table.add_column("Title", style="white", max_width=55)
    table.add_column("Analyzed", style="green", width=8, justify="center")

    for article in articles:
        analyzed = "Yes" if article["analyzed_at"] else "-"
        table.add_row(
            str(article["id"]),
            article["published_date"] or "-",
            article["title"][:55],
            analyzed,
        )

    console.print(table)
    console.print(f"\n[dim]Showing {len(articles)} of {get_article_count()} total[/]")


def cmd_stats(args):
    """Show statistics."""
    init_db()

    total = get_article_count()
    analyzed = get_analyzed_count()

    console.print(f"[bold]Total articles:    [/] {total}")
    console.print(f"[bold]Analyzed:          [/] {analyzed}")
    console.print(f"[bold]Pending analysis:  [/] {total - analyzed}")

    api_configured = bool(config.ANTHROPIC_API_KEY)
    email_configured = bool(config.SMTP_USER and config.EMAIL_TO)
    console.print(f"\n[bold]API Key configured:[/] {'Yes' if api_configured else '[red]No[/]'}")
    console.print(f"[bold]Email configured:  [/] {'Yes' if email_configured else '[red]No[/]'}")


def cmd_schedule(args):
    """Set up cron job for weekly execution."""
    import subprocess

    cron_cmd = f"0 9 * * 1 cd {config.PROJECT_ROOT} && {config.PROJECT_ROOT}/.venv/bin/python main.py weekly >> {config.PROJECT_ROOT}/output/cron.log 2>&1"

    console.print("[bold blue]Setting up weekly cron job...[/]")
    console.print(f"  Command: [dim]{cron_cmd}[/]")
    console.print("  Schedule: Every Monday at 9:00 AM")

    # Check existing crontab
    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        existing = result.stdout if result.returncode == 0 else ""
    except FileNotFoundError:
        existing = ""

    if "claude-blog-follower" in existing.lower() or "main.py weekly" in existing:
        console.print("[yellow]Cron job already exists.[/]")
        return

    new_crontab = existing.rstrip() + "\n# Claude Blog Follower - weekly digest\n" + cron_cmd + "\n"

    proc = subprocess.run(["crontab", "-"], input=new_crontab, text=True, capture_output=True)
    if proc.returncode == 0:
        console.print("[green]Cron job installed successfully![/]")
    else:
        console.print(f"[red]Failed to install cron job: {proc.stderr}[/]")


def main():
    parser = argparse.ArgumentParser(
        description="Claude Blog Follower - Track and analyze Anthropic's blog"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # fetch
    fetch_parser = subparsers.add_parser("fetch", help="Fetch articles from Anthropic")
    fetch_parser.add_argument("--all", action="store_true", help="Fetch all historical articles")
    fetch_parser.add_argument("--new", action="store_true", default=True, help="Fetch only new articles (default)")

    # analyze
    analyze_parser = subparsers.add_parser("analyze", help="Analyze articles with Claude API")
    analyze_parser.add_argument("--limit", type=int, help="Max articles to analyze")

    # report
    subparsers.add_parser("report", help="Generate HTML analysis report")

    # weekly
    subparsers.add_parser("weekly", help="Fetch new + analyze + send email digest")

    # list
    list_parser = subparsers.add_parser("list", help="List articles in database")
    list_parser.add_argument("--count", type=int, default=config.DEFAULT_DISPLAY_COUNT,
                             help="Number of articles to show")

    # stats
    subparsers.add_parser("stats", help="Show statistics")

    # schedule
    subparsers.add_parser("schedule", help="Set up weekly cron job")

    args = parser.parse_args()

    commands = {
        "fetch": cmd_fetch,
        "analyze": cmd_analyze,
        "report": cmd_report,
        "weekly": cmd_weekly,
        "list": cmd_list,
        "stats": cmd_stats,
        "schedule": cmd_schedule,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()
        sys.exit(1)
