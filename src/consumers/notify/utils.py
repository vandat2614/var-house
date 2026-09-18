"""
Utility functions for building LLM prompts from match data.
"""

from typing import List

from src.consumers.notify.prompts import SYSTEM_PROMPT, USER_PROMPT


def format_events(events: List[dict]) -> tuple[List[str], int, int]:
    """Extract and format match events into LLM-friendly text lines.

    Returns:
        (llm_events, final_home_score, final_away_score)
    """
    final_home_score = 0
    final_away_score = 0
    llm_events = ["--- BẮT ĐẦU HIỆP 1 ---"]
    half_number = 1

    for ev in events:
        minute = ev.get("minute", "?")
        event_type = ev.get("event_type", "")
        player = ev.get("player_name", "")

        if event_type == "Goal":
            h_score = ev.get("new_score_home", final_home_score)
            a_score = ev.get("new_score_away", final_away_score)
            final_home_score = h_score if h_score is not None else final_home_score
            final_away_score = a_score if a_score is not None else final_away_score

            is_own_goal = ev.get("is_own_goal", False)
            og_text = " (Own goal)" if is_own_goal else ""
            llm_events.append(f"[Goal] {minute}\' - {player}{og_text} ({final_home_score} - {final_away_score})")

        elif event_type == "Card":
            card_type = ev.get("card_type", "")
            if card_type in ["Red", "YellowRed"]:
                llm_events.append(f"[Red Card] {minute}\' - {player}")
            elif card_type == "Yellow":
                llm_events.append(f"[Yellow Card] {minute}\' - {player}")

        elif event_type == "Substitution":
            p_in = ev.get("player_in_name", "")
            p_out = ev.get("player_out_name", "")
            llm_events.append(f"[Substitution] {minute}\' - In: {p_in} | Out: {p_out}")

        elif event_type == "Half":
            llm_events.append(f"--- KẾT THÚC HIỆP {half_number} ---")
            half_number += 1
            if half_number <= 2:
                llm_events.append(f"--- BẮT ĐẦU HIỆP {half_number} ---")

    return llm_events, final_home_score, final_away_score


def format_stats(stats: List[dict]) -> str:
    """Format top stats into a text block for the LLM prompt."""
    if not stats:
        return ""
    stats_lines = []
    for stat in stats:
        if stat.get("group") == "Top stats":
            title = stat.get("stat_title")
            hv = stat.get("home_value")
            av = stat.get("away_value")
            stats_lines.append(f"- {title}: {hv} (Home) vs {av} (Away)")
    if stats_lines:
        return "\nTHỐNG KÊ TRẬN ĐẤU:\n" + "\n".join(stats_lines)
    return ""


def build_messages(
    home_team: str,
    away_team: str,
    home_score: int,
    away_score: int,
    events_text: str,
    stats_text: str,
) -> list[dict]:
    """Build the system + user message list for the LLM."""
    user_content = USER_PROMPT.format(
        home_team=home_team,
        away_team=away_team,
        home_score=home_score,
        away_score=away_score,
        events_text=events_text,
        stats_text=stats_text,
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
