import browser_cookie3 as bc3
import requests
import json


def get_contest_result(contest_id, browser):
    """
    Returns the contest result of the contest with the given contest_id as a JSON
    """
    match browser:
        case "chrome":
            cookie = bc3.chrome()
        case "firefox":
            cookie = bc3.firefox()
    r = requests.get(
        f"https://vjudge.net/contest/rank/single/{contest_id}",
        cookies=cookie,
        timeout=10,
    )
    return r.text


def parse_contest_result(orig_s: str):
    """
    Returns a saner dictionary from consuming the API.

    The dictionary returned by this function is of the form:

    {
        "contest_id": 123,
        "contest_name": "Contest Name",
        "prob_count": 5,
        "duration": 18000000,
        "participants": {
            "username1": "Real Name 1",
            "username2": "Real Name 2",
            ...
        },
        "results": {
            "username1": {
                "insolved": 3,
                "upsolved": 1,
                "penalty": 1000,
                "detail": [penalty1, penalty2, ...],
            }
        }
    }
    """
    orig = json.loads(orig_s)
    ret = dict()
    # Get the participants out
    ret["contest_id"] = orig["id"]
    ret["contest_name"] = orig["title"]
    duration = ret["duration"] = orig["length"] / 1000
    ret["participants"] = dict()
    ret["results"] = dict()
    id_to_username = dict()
    for id, participant in orig["participants"].items():
        ret["participants"][participant[0]] = participant[1]
        id_to_username[id] = participant[0]

    # Get the results out
    submissions = orig["submissions"]
    submissions.sort(key=lambda x: x[3])
    prob_count = ret["prob_count"] = max(submission[1] for submission in submissions)
    print(prob_count)

    # Temporarily keep track of number of failed submissions
    # Because penalty won't be added if the user didn't solve the problem
    failed_submissions = dict()
    for submission in submissions:
        username = id_to_username[str(submission[0])]
        if username not in ret["results"]:
            ret["results"][username] = {
                "upsolved": 0,
                "insolved": 0,
                "penalty": 0,
                "detail": [0] * (prob_count + 1), 
            }
        uid, pid, status, time = submission[0], submission[1], submission[2], submission[3]
        if status == 1:
            if time > duration:
                # upsolve
                if ret["results"][username]["detail"][pid] != 0:
                    continue
                ret["results"][username]["upsolved"] += 1
                ret["results"][username]["detail"][pid] = -1
            else:
                # solve
                if ret["results"][username]["detail"][pid] != 0:
                    continue
                ret["results"][username]["insolved"] += 1
                ret["results"][username]["penalty"] += time + failed_submissions.get(
                    (username, pid), 0
                ) *  20 * 60 * 1000
                ret["results"][username]["detail"][pid] = time
        else:
            # not solve
            failed_submissions[(username, pid)] = (
                failed_submissions.get((username, pid), 0) + 1
            )

    return ret

if __name__ == "__main__":
    print(parse_contest_result(get_contest_result(641744, "firefox")))
