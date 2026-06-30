from agents.gemini_client import model


def predict_risk(
    task,
    deadline
):

    prompt = f"""
Predict likelihood of missing deadline.

Task:
{task}

Deadline:
{deadline}

Return:

Risk Score:
Reason:
Action:
"""

    response = model.generate_content(
        prompt
    )

    return response.text