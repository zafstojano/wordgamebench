import json
import os
import uuid

import boto3
import requests

from src.game_engine import HARD_CAP_MAX_ATTEMPTS
from src.game_manager import ConnectionsGameManager, WordleGameManager

MODELS = [
    "anthropic/claude-3-haiku",
    "anthropic/claude-3-opus",
    "anthropic/claude-3.5-sonnet",
    "google/gemini-flash-1.5",
    "google/gemini-pro-1.5",
    "google/gemma-2-27b-it",
    "google/gemma-2-9b-it",
    "meta-llama/llama-3.1-405b-instruct",
    "meta-llama/llama-3.1-70b-instruct",
    "meta-llama/llama-3.1-8b-instruct",
    "mistralai/mistral-large",
    "mistralai/mistral-small",
    "mistralai/mistral-tiny",
    "nousresearch/hermes-3-llama-3.1-405b",
    "nousresearch/hermes-3-llama-3.1-70b",
    "openai/chatgpt-4o-latest",
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
]
PUZZLES = ["wordle", "connections"]

GH_PAT = os.environ.get("GH_PAT")
WGB_TABLE = os.environ.get("WGB_TABLE")
WGB_BUCKET = os.environ.get("WGB_BUCKET")
WGB_GH_ACTION_URL = os.environ.get("WGB_GH_ACTION_URL")


def eval(config):
    print("Evaluating for config:", config)
    puzzle = config["puzzle"]
    content = config["content"]
    date = config["date"]
    prompt_manager_path = f"src/prompts/{puzzle}"

    daily_results = []

    for model_id in MODELS:
        if puzzle == "wordle":
            game_manager = WordleGameManager(content, model_id, prompt_manager_path)
        elif puzzle == "connections":
            game_manager = ConnectionsGameManager(
                content, model_id, prompt_manager_path
            )
        else:
            raise ValueError(f"Invalid puzzle: {puzzle}")

        print(f"Puzzle: {puzzle}, Model: {model_id}, Content: {content}")
        try:
            result = game_manager.play()
            messages = game_manager.format_messages()
            num_attempts = game_manager.get_total_num_attempts()
        except Exception as e:
            print(f"Exception occurred: {str(e)}")
            print(f"Couldn't play the game for model: {model_id}")
            result = 0
            messages = json.dumps([])
            num_attempts = HARD_CAP_MAX_ATTEMPTS

        print("Saving the result to DynamoDB...")
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(WGB_TABLE)

        data = {
            "model_id": model_id,
            "puzzle": puzzle,
            "result": result,
            "messages": messages,
            "date": date,
            "attempts": num_attempts,
        }
        table.put_item(Item=({"id": str(uuid.uuid4())} | data))
        daily_results.append(data)

    print("Saving daily results to s3...")
    try:
        s3 = boto3.client("s3")
        s3.put_object(
            Body=json.dumps(daily_results),
            Bucket=WGB_BUCKET,
            Key=f"daily_{puzzle}.json",
        )
    except Exception as e:
        print("Couldn't save results to s3.")
        raise e
    print("Results saved successfully.")


def _process_items(items, results):
    for item in items:
        model_id = item.get("model_id")
        puzzle = item.get("puzzle")
        result = int(item.get("result", 0))
        attempts = item.get("attempts", None)

        if model_id not in results:
            results[model_id] = {}
        if puzzle not in results[model_id]:
            results[model_id][puzzle] = {
                "score": 0,
                "count": 0,
                "attempts": 0,
                "attempts_count": 0,
            }

        results[model_id][puzzle]["score"] += result
        results[model_id][puzzle]["count"] += 1
        if attempts is not None:
            results[model_id][puzzle]["attempts"] += int(attempts)
            results[model_id][puzzle]["attempts_count"] += 1


def summarize():
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(WGB_TABLE)
    results = {}

    print("Scanning the table...")
    try:
        response = table.scan()
        while True:
            _process_items(response["Items"], results)
            if "LastEvaluatedKey" not in response:
                break
            response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
    except Exception as e:
        print("Couldn't scan the table.")
        raise e

    print("Summarizing the results...")
    summarized_results = {}

    for model_id in results:
        summarized_results[model_id] = {"model_id": model_id, "average_score": 0}
        for puzzle in PUZZLES:
            if puzzle not in results[model_id]:
                summarized_results[model_id][f"{puzzle}_count"] = 0
                summarized_results[model_id][f"{puzzle}_score"] = 0
                summarized_results[model_id][f"{puzzle}_avg_attempts"] = 0
                continue
            summarized_results[model_id][f"{puzzle}_count"] = results[model_id][puzzle][
                "count"
            ]
            summarized_results[model_id][f"{puzzle}_score"] = (
                results[model_id][puzzle]["score"] / results[model_id][puzzle]["count"]
            )
            if results[model_id][puzzle]["attempts_count"] > 0:
                summarized_results[model_id][f"{puzzle}_avg_attempts"] = (
                    results[model_id][puzzle]["attempts"]
                    / results[model_id][puzzle]["attempts_count"]
                )
            else:
                summarized_results[model_id][f"{puzzle}_avg_attempts"] = 0
            summarized_results[model_id]["average_score"] += summarized_results[
                model_id
            ][f"{puzzle}_score"]
        summarized_results[model_id]["average_score"] /= len(PUZZLES)

    print("Saving summarized results to s3...")
    s3 = boto3.client("s3")
    try:
        s3.put_object(
            Body=json.dumps(list(summarized_results.values())),
            Bucket=WGB_BUCKET,
            Key="results.json",
        )
    except Exception as e:
        print("Couldn't save results to s3.")
        raise e
    print("Results saved successfully.")


def trigger_gh_action():
    print("Triggering GitHub Action...")
    headers = {
        "Authorization": f"token {GH_PAT}",
        "Accept": "application/vnd.github.v3+json",
    }
    data = {"ref": "main"}
    response = requests.post(WGB_GH_ACTION_URL, headers=headers, json=data)
    if response.status_code == 204:
        print("GitHub Action triggered successfully!")
    else:
        print(f"Failed to trigger GitHub Action. Status code: {response.status_code}")
        print(f"Response: {response.text}")


if __name__ == "__main__":
    configs = json.loads(os.environ.get("WGB_CONFIG"))
    for config in configs:
        eval(config)
    summarize()
    trigger_gh_action()
