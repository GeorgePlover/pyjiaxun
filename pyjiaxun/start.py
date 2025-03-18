#!/usr/bin/env python
import click
import csv, sys
from rich.console import Console
from rich.table import Table
from peewee import DoesNotExist

# Import your crawling and DB modules. Adjust these imports as necessary.
import pyjiaxun.crawl as crawl
from pyjiaxun.data import (
    Contest,
    User,
    Participation,
    ContestGroup,
    ContestGroupContest,
    manage_a_group_of_contests,
    import_contest_results,
    db,
)  # adjust this to your actual module path

console = Console()

@click.group()
@click.option("--browser", "-b", default="firefox", help="Browser to use for crawling.")
def cli(browser):
    pass

@cli.group()
def database():
    """Database related commands."""
    pass


# Create a group for user-related commands.
@cli.group()
def user():
    """User related commands."""
    pass

@cli.group()
def contest():
    """Contest related commands."""
    pass

@cli.group()
def contestgroup():
    """Contest Group related commands."""
    pass

@database.command()
def init():
    """
    Initialize the databases.
    """
    with db:
        db.create_tables([Contest, User, Participation, ContestGroup, ContestGroupContest])
    console.print("[bold green]Database initialized successfully.[/bold green]")


@database.command()
def reset():
    """
    Deletes the current tables and recreates them.
    """
    console.print("[bold red]Dropping all tables and recreating them...[/bold red]")
    with db:
        db.drop_tables([Contest, User, Participation, ContestGroup, ContestGroupContest])
        db.create_tables([Contest, User, Participation, ContestGroup, ContestGroupContest])
    console.print("[bold green]Database reset successfully.[/bold green]")


@contest.command("get")
@click.argument("contest_id")
def get(contest_id):
    """
    Parse the contest (using the crawl API) and store it in the DB.

    Example: pyjiaxun get CODE123
    """
    console.print(f"[bold blue]Fetching contest {contest_id}...[/bold blue]")
    raw_result = crawl.get_contest_result(contest_id, browser="firefox")
    if not raw_result:
        console.print("[bold red]Failed to retrieve contest data.[/bold red]")
        return

    parsed_result = crawl.parse_contest_result(raw_result)
    if not parsed_result:
        console.print("[bold red]Failed to parse contest data.[/bold red]")
        return
    try:
        import_contest_results(parsed_result)
    except Exception:
        console.print("[bold red]Failed to import contest data.[/bold red]")
        console.print("[yellow]Maybe you forgot to initialize the database?[/yellow]")
        return
    contest_name = parsed_result.get("contest_name", contest_id)
    console.print(
        f"[bold green]Contest '{contest_name}' imported successfully.[/bold green]"
    )




@user.command("info")
@click.argument("username")
@click.option(
    "--sort",
    "-s",
    default="insolved",
    help="Sort by insolved, upsolved or total solved.",
)
def user_info(username, sort):
    """
    Print an aggregate report of the user.

    Example: pyjiaxun user info alice
    """
    try:
        user_obj = User.get(User.username == username)
    except DoesNotExist:
        console.print(f"[bold red]User '{username}' not found in database.[/bold red]")
        return

    total_insolved = 0
    total_upsolved = 0

    table = Table(title=f"Aggregate Report for {username}")
    table.add_column("Contest", style="cyan")
    table.add_column("Insolved", justify="right")
    table.add_column("Upsolved", justify="right")
    table.add_column("Total", justify="right")

    # Determine sort order based on the sort option.
    if sort.startswith("insolve"):
        order = Participation.problem_status["insolved"].desc()
    elif sort.startswith("upsolve"):
        order = Participation.problem_status["upsolved"].desc()
    else:
        # sort by insolved + upsolved
        order = (
            Participation.problem_status["insolved"]
            + Participation.problem_status["upsolved"]
        ).desc()

    for participation in user_obj.participations.order_by(order):
        # Assume participation.problem_status is a dict containing keys "insolved" and "upsolved"
        result = (
            participation.problem_status
            if isinstance(participation.problem_status, dict)
            else {}
        )
        insolved = result.get("insolved", 0)
        upsolved = result.get("upsolved", 0)
        total = insolved + upsolved
        total_insolved += insolved
        total_upsolved += upsolved

        table.add_row(
            participation.contest.name, str(insolved), str(upsolved), str(total)
        )

    console.print(table)
    overall = total_insolved + total_upsolved
    console.print(
        f"[bold]Overall Totals[/bold]: Insolved: {total_insolved}, Upsolved: {total_upsolved}, Total: {overall}"
    )


@user.command("untrack")
@click.argument("username")
def user_untrack(username):
    """
    Set the user's inteam field to False to ignore this user.

    Example: pyjiaxun user untrack alice
    """
    try:
        user_obj = User.get(User.username == username)
    except DoesNotExist:
        console.print(f"[bold red]User '{username}' not found in database.[/bold red]")
        return

    user_obj.inteam = False
    user_obj.save()
    console.print(f"[bold green]User '{username}' is now untracked.[/bold green]")


@user.command("track")
@click.argument("username")
def user_track(username):
    """
    Set the user's inteam field to True to track this user.

    Example: pyjiaxun user track alice
    """
    try:
        user_obj = User.get(User.username == username)
    except DoesNotExist:
        console.print(f"[bold red]User '{username}' not found in database.[/bold red]")
        return

    user_obj.inteam = True
    user_obj.save()
    console.print(f"[bold green]User '{username}' is now tracked.[/bold green]")


@contest.command("info")
@click.argument("contest_id")
@click.option(
    "--sort",
    "-s",
    default="insolved",
    help="Sort by insolved, upsolved or total solved.",
)
def contest_info(contest_id, sort):
    """
    If the contest is already parsed, report it.

    Example: pyjiaxun contest CODE123
    """
    try:
        contest_obj = Contest.get(Contest.id == contest_id)
    except DoesNotExist:
        console.print(
            f"[bold red]Contest '{contest_id}' not found in database.[/bold red]"
        )
        return

    console.print(f"[bold green]Contest:[/bold green] {contest_obj.name}")
    console.print(f"[bold green]Duration:[/bold green] {contest_obj.duration}")
    console.print(f"[bold green]Problem Count:[/bold green] {contest_obj.prob_count}")

    table = Table(title=f"Participants in {contest_obj.name}")
    table.add_column("Username", style="cyan")
    table.add_column("Real Name", style="magenta")
    table.add_column("Insolved", justify="right")
    table.add_column("Upsolved", justify="right")
    table.add_column("Total Solved", justify="right")

    # Determine sort order based on the sort option.
    if sort.startswith("insolve"):
        order = Participation.problem_status["insolved"].desc()
    elif sort.startswith("upsolve"):
        order = Participation.problem_status["upsolved"].desc()
    else:
        # sort by insolved + upsolved
        order = (
            Participation.problem_status["insolved"]
            + Participation.problem_status["upsolved"]
        ).desc()

    for participation in contest_obj.participations.order_by(order):
        user_obj = participation.user
        if user_obj.inteam is False:
            continue
        result = (
            participation.problem_status
            if isinstance(participation.problem_status, dict)
            else {}
        )
        insolved = str(result.get("insolved", 0))
        upsolved = str(result.get("upsolved", 0))
        tot_solved = str(result.get("insolved", 0) + result.get("upsolved", 0))
        table.add_row(user_obj.username, user_obj.realname, insolved, upsolved, tot_solved)

    console.print(table)


@contest.command("dump")
@click.argument("contest_id")
def dump_contest(contest_id):
    """
    Dump contest participation data as CSV.

    Example: pyjiaxun dump contest CODE123
    """
    try:
        # Adjust query as needed (Contest.id vs Contest.name).
        contest_obj = Contest.get(Contest.id == contest_id)
    except DoesNotExist:
        console.print(f"[bold red]Contest '{contest_id}' not found in database.[/bold red]")
        return

    writer = csv.writer(sys.stdout)
    writer.writerow(["Username", "Real Name", "Insolved", "Upsolved", "Penalty"])
    for participation in contest_obj.participations:
        user_obj = participation.user
        result = participation.problem_status if isinstance(participation.problem_status, dict) else {}
        insolved = result.get("insolved", 0)
        upsolved = result.get("upsolved", 0)
        penalty = result.get("penalty", 0)
        writer.writerow([user_obj.username, user_obj.realname, insolved, upsolved, penalty])


@user.command("dump")
@click.argument("username")
def dump_user(username):
    """
    Dump user participation data as CSV.

    Example: pyjiaxun dump user alice
    """
    try:
        user_obj = User.get(User.username == username)
    except DoesNotExist:
        console.print(f"[bold red]User '{username}' not found in database.[/bold red]")
        return

    writer = csv.writer(sys.stdout)
    writer.writerow(["Contest", "Insolved", "Upsolved", "Total"])
    for participation in user_obj.participations:
        result = participation.problem_status if isinstance(participation.problem_status, dict) else {}
        insolved = result.get("insolved", 0)
        upsolved = result.get("upsolved", 0)
        total = insolved + upsolved
        writer.writerow([participation.contest.name, insolved, upsolved, total])

@contest.command("list")
def contest_list():
    """
    List all contests in the database.

    Example: pyjiaxun contest-list
    """
    table = Table(title="Contest List")
    table.add_column("ID", justify="right")
    table.add_column("Name", style="cyan")
    table.add_column("Duration", justify="right")
    table.add_column("Problem Count", justify="right")
    table.add_column("Participants", justify="right")

    for contest in Contest.select():
        # Count the number of participations for the contest.
        participants_count = contest.participations.count()
        table.add_row(
            str(contest.id),
            contest.name,
            str(contest.duration),
            str(contest.prob_count),
            str(participants_count),
        )

    console.print(table)
    
@contestgroup.command("create")
@click.argument("group_name")
def create_contest_group(group_name):
    """
    Create a new contest group.

    Example: pyjiaxun contestgroup create group1
    """
    try:
        ContestGroup.get(ContestGroup.name == group_name)
        console.print(f"[bold red]Contest group '{group_name}' already exists.[/bold red]")
        return
    except DoesNotExist:
        manage_a_group_of_contests({"name": group_name, "contests": [], "description": "", "options": "create"})
        console.print(f"[bold green]Contest group '{group_name}' created successfully.[/bold green]")

@contestgroup.command("addcontest")
@click.argument("group_name")
@click.argument("contest_id")
def add_contest_to_group(group_name, contest_id):
    """
    Add a contest to a group.

    Example: pyjiaxun contestgroup addcontest group1 CODE123
    """
    try:
        group_obj = ContestGroup.get(ContestGroup.name == group_name)
    except DoesNotExist:
        console.print(f"[bold red]Contest group '{group_name}' not found in database.[/bold red]")
        return

    try:
        contest_obj = Contest.get(Contest.id == contest_id)
    except DoesNotExist: # 比赛不在数据库中，自动调用contest get命令抓取
        console.print(f"[bold]Contest '{contest_id}' not found in database, trying to fetch it...[/bold]")
        get(contest_id)
        return

    try:
        ContestGroupContest.get(ContestGroupContest.contest_id == contest_obj.id, ContestGroupContest.contest_group_id == group_obj.id)
        console.print(f"[bold red]Contest '{contest_obj.name}' is already in group '{group_name}'.[/bold red]")
        return
    except DoesNotExist:
        manage_a_group_of_contests({"name": group_name, "contests": [contest_id], "description": "", "options": "add"})
        console.print(f"[bold green]Contest '{contest_obj.name}' added to group '{group_name}' successfully.[/bold green]")
        
@contestgroup.command("removecontest")
@click.argument("group_name")
@click.argument("contest_id")
def remove_contest_from_group(group_name, contest_id):
    """
    Remove a contest from a group.

    Example: pyjiaxun contestgroup removecontest group1 CODE123
    """
    try:
        group_obj = ContestGroup.get(ContestGroup.name == group_name)
    except DoesNotExist:
        console.print(f"[bold red]Contest group '{group_name}' not found in database.[/bold red]")
        return

    try:
        contest_obj = Contest.get(Contest.id == contest_id)
    except DoesNotExist:
        console.print(f"[bold red]Contest '{contest_id}' not found in database.[/bold red]")
        return

    try:
        ContestGroupContest.get(ContestGroupContest.contest_id == contest_obj.id, ContestGroupContest.contest_group_id == group_obj.id)
        manage_a_group_of_contests({"name": group_name, "contests": [contest_id], "description": "", "options": "remove"})
        console.print(f"[bold green]Contest '{contest_obj.name}' removed from group '{group_name}' successfully.[/bold green]")
    except DoesNotExist:
        console.print(f"[bold red]Contest '{contest_obj.name}' is not in group '{group_name}'.[/bold red]")



if __name__ == "__main__":
    # pylint: disable=no-value-for-parameter
    cli()
