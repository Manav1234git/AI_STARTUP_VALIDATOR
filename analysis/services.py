from .ai_service import call_ai

def run_analysis(idea, audience, problem):
    prompt = f"""
    Analyze this startup idea:

    Idea: {idea}
    Audience: {audience}
    Problem: {problem}

    Give:
    - feasibility (0-100)
    - market demand
    - competition
    - strengths
    - weaknesses
    """

    response = call_ai(prompt)

    return {
        "raw": response
    }