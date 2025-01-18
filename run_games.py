import subprocess
import threading
import re
import time

# Global statistics dictionary to track wins and times
statistics = {
    "ChatGPT": {"wins": 0, "white_wins": 0, "black_wins": 0},
    "Gemini": {"wins": 0, "white_wins": 0, "black_wins": 0},
    "total_games": 0,
    "total_time": 0.0
}

def parse_game_result(output):
    """Parses the output of a game to extract the winner, color, and game duration."""
    winner_match = re.search(r"Result: (White|Black) wins \((ChatGPT|Gemini)\)", output)
    time_match = re.search(r"Elapsed Time: ([\d.]+) seconds", output)

    if not winner_match or not time_match:
        return None, None, None

    color, winner = winner_match.groups()
    game_time = float(time_match.group(1))

    return winner, color, game_time

def run_game(game_id):
    """Runs a single game and updates statistics based on the result."""
    global statistics
    print(f"Starting game {game_id}...")
    result = subprocess.run(["python", "ui.py"], capture_output=True, text=True)
    output = result.stdout

    winner, color, game_time = parse_game_result(output)
    if winner and color and game_time is not None:
        # Update statistics
        statistics["total_games"] += 1
        statistics["total_time"] += game_time
        statistics[winner]["wins"] += 1

        if color == "White":
            statistics[winner]["white_wins"] += 1
        elif color == "Black":
            statistics[winner]["black_wins"] += 1

    print(f"Game {game_id} finished. Output: {output}")

def main():
    global statistics
    threads = []
    num_games = 10

    # Start the games in separate threads
    for i in range(num_games):
        thread = threading.Thread(target=run_game, args=(i+1,))
        threads.append(thread)
        thread.start()

    # Wait for all threads to finish
    for thread in threads:
        thread.join()

    # Calculate win percentages and average time
    total_games = statistics["total_games"]
    if total_games > 0:
        statistics["ChatGPT"]["win_percentage"] = (statistics["ChatGPT"]["wins"] / total_games) * 100
        statistics["Gemini"]["win_percentage"] = (statistics["Gemini"]["wins"] / total_games) * 100
        statistics["average_time"] = statistics["total_time"] / total_games

    # Print final statistics
    print("\nGame Statistics:")
    print(f"Total Games: {total_games}")
    print(f"ChatGPT Wins: {statistics['ChatGPT']['wins']} ({statistics['ChatGPT']['win_percentage']:.2f}%)")
    print(f"ChatGPT Wins as White: {statistics['ChatGPT']['white_wins']}")
    print(f"ChatGPT Wins as Black: {statistics['ChatGPT']['black_wins']}")
    print(f"Gemini Wins: {statistics['Gemini']['wins']} ({statistics['Gemini']['win_percentage']:.2f}%)")
    print(f"Gemini Wins as White: {statistics['Gemini']['white_wins']}")
    print(f"Gemini Wins as Black: {statistics['Gemini']['black_wins']}")
    print(f"Average Time per Game: {statistics['average_time']:.2f} seconds")

if __name__ == "__main__":
    main()
