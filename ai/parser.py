"""
AI Parser — converts natural language sports queries into structured JSON.

Runs locally using a Hugging Face model (no APIs or Ollama).
You can swap in any instruction-tuned model like Mistral, Phi-3, or Llama-3.
"""

import json
from perplexity import Perplexity

# -----------------------------
# 📊  Default Metrics Mapping
# -----------------------------
# Maps stat_type to default metrics if metric is missing or null
DEFAULT_METRICS = {
    "standard": ["goals", "assists", "minutes"],
    "keeper": ["saves", "clean sheets", "goals conceded"],
    "shooting": ["shots", "shots on target", "goals"],
    "passing": ["passes completed", "pass accuracy", "passes attempted"],
    "defense": ["tackles", "interceptions", "clearances"],
    "possession": ["possession %", "touches", "dribbles completed"],
}

# -----------------------------
# 🧠  Prompt Template
# -----------------------------
SYSTEM_PROMPT = """
You are a sports analytics parsing assistant.

Your task is to extract *only* the information explicitly mentioned in a user's natural language query about sports performance.
Do NOT infer or assume any data. If something is not clearly stated in the query, return null for that field.

Specifically:
- Only extract `metric` if it is explicitly mentioned (e.g. "xG", "goals", "key passes").
- If the query says "passing stats", "shooting stats", etc., but no specific metric (like "key passes" or "xG"), return `"metric": null`.
- Do not guess or list common metrics — that will be handled programmatically after parsing.
- Do not include information that was not in the query.
- If no player or team is mentioned, return null for those fields, do NOT infer.
- For season: always use compact format (e.g. "2324" for 2023/24), not "2023-24".

Also, choose the most appropriate chart type for visualization if not specified.

Return ONLY valid JSON with the following fields:
{
  "team": string or list of strings or null,
  "league": string or null (options: 'Big 5 European Leagues Combined','ENG-Premier League','ESP-La Liga','FRA-Ligue 1','GER-Bundesliga','INT-European Championship','INT-Women's World Cup','INT-World Cup','ITA-Serie A'),
  "player": string or list of strings or null,
  "season": string or list of strings or null (format "2324" for 2023/24 season or ['20','21','22'] for [2020/21, 2021/22 and 2022/23 seasons]),
  "stat_type": string (options: "standard", "keeper", "shooting", "passing", "defense", "possession"),
  "metric": string or list of strings or null,
  "metric_type": string or null (options: "team", "player", "match", "league", null),
  "chart_type": string or null (options: "bar", "line", "scatter", "pie", "table", "heatmap", "radar")
}

If something is not mentioned, use null. 
Output must be valid JSON — no explanations, no text before or after.
"""

# -----------------------------
# 🚀  Core Function
# -----------------------------
def parse_prompt(prompt: str, max_tokens: int = 200) -> dict:
    """
    Parse a natural language sports query into structured JSON fields using the Perplexity API.
    """
    client = Perplexity()

    try:
        completion = client.chat.completions.create(
            model="sonar-pro",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=max_tokens,
        )
    except Exception as e:
        print("API request failed:", e)
        return {"team": None, "league": None, "player": None, "season": None, "stat_type": None, "metric": None, "metric_type": None, "chart_type": None}

    # Extract text safely
    text = completion.choices[0].message.content.strip() if completion.choices else ""
    if not text:
        print("Empty response from API.")
        return {"team": None, "league": None, "player": None, "season": None, "stat_type": None, "metric": None, "metric_type": None, "chart_type": None}

    # Extract JSON safely
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        print("No JSON found in model output:", text)
        return {"team": None, "league": None, "player": None, "season": None, "stat_type": None, "metric": None, "metric_type": None, "chart_type": None}

    try:
        parsed = json.loads(text[start:end + 1])
        # If "metric" is missing or null, assign defaults based on "stat_type"
        if "metric" not in parsed or parsed["metric"] is None:
            stat_type = parsed.get("stat_type")
            if stat_type in DEFAULT_METRICS:
                parsed["metric"] = DEFAULT_METRICS[stat_type]
            else:
                parsed["metric"] = ["all"]
        return parsed
    except json.JSONDecodeError:
        print("Invalid JSON, raw output:", text)
        return {"team": None, "league": None, "player": None, "season": None, "metric": None, "metric_type": None, "chart_type": None}

# -----------------------------
# 🧪  Local Test
# -----------------------------
if __name__ == "__main__":
    examples = [
        "Show me Arsenal's expected goals in the 2023 Premier League season",
        "Compare Real Madrid and Barcelona goals in La Liga 2022/23",
        "Liverpool possession stats past 5 seasons",
        "Show me Manchester United passing stats this season",
        "Top 10 goalkeepers in Serie A 2021/22 by clean sheets",
    ]

    for q in examples:
        print(f"\n🗣️ Prompt: {q}")
        result = parse_prompt(q)
        print("🧩 Parsed:", result)