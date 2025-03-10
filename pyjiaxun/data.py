from peewee import (
    Model,
    CharField,
    BooleanField,
    IntegerField,
    DateTimeField,
    ForeignKeyField,
    CompositeKey,
    SqliteDatabase,
    DoesNotExist,
)
from playhouse.sqlite_ext import JSONField
import os
from appdirs import user_data_dir

APP_NAME = "pyjiaxun"
APP_AUTHOR = "Lily White"  # optional, useful on Windows

# Get a directory for storing user-specific application data.
data_dir = user_data_dir(APP_NAME, APP_AUTHOR)
os.makedirs(data_dir, exist_ok=True)

# Now define your database path
db_path = os.path.join(data_dir, "pyjiaxun.sqlite")

# Initialize a SQLite database (adjust the path as needed)
db = SqliteDatabase(db_path)


class BaseModel(Model):
    class Meta:
        database = db


class User(BaseModel):
    """
    Represents a user.
    """

    username = CharField(primary_key=True)
    realname = CharField()
    inteam = BooleanField()

    def __str__(self):
        return f"User({self.username})"


class Contest(BaseModel):
    """
    Represents a contest.
    """
    id = IntegerField(primary_key=True)
    name = CharField()
    start_time = IntegerField()
    duration = IntegerField()
    prob_count = IntegerField()
    problems = JSONField()  # Stores list[str]

    # Participants can be accessed via the backref on Participation (i.e. contest.participations)

    def __str__(self):
        return f"Contest({self.name})"

class ContestGroup(BaseModel):
    """
    Represents a group of contests.
    """
    id = IntegerField(primary_key=True)
    name = CharField()
    description = CharField()
    update_date = DateTimeField()

class Participation(BaseModel):
    """
    Represents a user's participation in a contest.
    """

    contest = ForeignKeyField(Contest, backref="participations")
    user = ForeignKeyField(User, backref="participations")
    problem_status = JSONField()

    class Meta:
        # Ensure that each (user, contest) pair is unique
        primary_key = CompositeKey("contest", "user")

    def __str__(self):
        return (
            f"Participation(User: {self.user.username}, Contest: {self.contest.name})"
        )

class ContestGroupContest(BaseModel):
    """
    Represents a relationship between a contest and a group of contests.
    """
    group = ForeignKeyField(ContestGroup, backref="contests")
    contest = ForeignKeyField(Contest, backref="groups")

    class Meta:
        # Ensure that each (group, contest) pair is unique
        primary_key = CompositeKey("group", "contest")

    def __str__(self):
        return (
            f"ContestGroupContest(Contest: {self.contest.name}, Group: {self.group.name})"
        )

def import_contest_results(api_data: dict):
    """
    Imports contest results from the API into the database.
    """
    with db.atomic():
        # Create or get the contest.
        # Since our Contest model uses 'name' as primary key, we use contest_name.
        contest, created = Contest.get_or_create(
            id=api_data["contest_id"],
            name=api_data["contest_name"],
            defaults={
                "duration": api_data["duration"],
                "prob_count": api_data["prob_count"],
                "start_time": 0,  # No start_time provided by API, default to 0.
                "problems": [],  # No problems list from API, so default to empty.
            },
        )
        if created:
            print(f"Contest '{contest.id}' created.")
        else:
            print(f"Contest '{contest.id}' already exists.")

        # Insert or update users.
        for username, realname in api_data["participants"].items():
            user, created = User.get_or_create(
                username=username,
                defaults={
                    "realname": realname,
                    "inteam": True,  # Default value since API doesn't provide this.
                },
            )
            if created:
                print(f"User '{username}' created.")
            else:
                # Optionally update the real name if it has changed.
                if user.realname != realname:
                    user.realname = realname
                    user.save()
                    print(f"User '{username}' updated.")

        # Insert participation records for each result.
        for username, result in api_data["results"].items():
            try:
                user = User.get(User.username == username)
            except DoesNotExist:
                print(
                    f"Warning: User '{username}' from results not found in participants."
                )
                continue

            # Here we store only the 'detail' list in our problem_status field.
            # You can modify this to include 'insolved', 'upsolved', or 'penalty' if needed.
            participation, created = Participation.get_or_create(
                contest=contest,
                user=user,
                defaults={"problem_status": result},
            )
            if created:
                print(
                    f"Participation for user '{username}' in contest '{contest.name}' created."
                )
            else:
                # If the record exists, you might update it if the API data has changed.
                participation.problem_status = result
                participation.save()
                print(
                    f"Participation for user '{username}' in contest '{contest.name}' updated."
                )


def get_participations_by_user(username: str):
    """
    Retrieve all participation records for a given user by username.

    :param username: The username of the user.
    :return: A list of Participation objects for that user.
    """
    try:
        user = User.get(User.username == username)
    except DoesNotExist:
        print(f"User '{username}' does not exist.")
        return []

    # Using the backref from User to Participation:
    return list(user.participations)


def get_participations_by_contest(contest_name: str):
    """
    Retrieve all participation records for a given contest by contest name.

    :param contest_name: The name of the contest.
    :return: A list of Participation objects for that contest.
    """
    try:
        contest = Contest.get(Contest.name == contest_name)
    except DoesNotExist:
        print(f"Contest '{contest_name}' does not exist.")
        return []

    # Using the backref from Contest to Participation:
    return list(contest.participations)


def init_db():
    """
    Initialize the database by creating tables if they do not exist.
    """
    with db:
        db.create_tables([User, Contest, Participation])
