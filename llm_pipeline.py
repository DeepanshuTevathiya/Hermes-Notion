"""
Groq LLM Pipeline module.
Handles:
  1. ATS Scoring & JD Gap identification.
  2. Safe Resume Tailoring (strictly truthful, no hallucinated skills, emphasizes true matches).
  3. Personalized cold outreach email drafting.
"""

import json
import re
from groq import Groq

# Fast and strong available reasoning model on Groq
MODEL_NAME = "openai/gpt-oss-120b"


def get_groq_client(api_key: str) -> Groq:
    """Initialize Groq API client."""
    return Groq(api_key=api_key)


def _extract_json_from_text(text: str) -> dict:
    """Safely extract JSON object from LLM response text."""
    if not text:
        return {}
    # Find { ... }
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass
    try:
        return json.loads(text)
    except Exception:
        return {}


def score_and_identify_gaps(client: Groq, resume_text: str, jd_text: str) -> dict:
    """
    Compare resume vs job description to generate:
      - ats_score: 0 to 100
      - jd_summary: short overview of role requirements
      - matching_skills: list of skills candidate actually has that match JD
      - missing_skills: list of skills in JD that candidate lacks (gaps)
    """
    prompt = f"""You are an ATS and Technical Recruiter. Evaluate candidate's real resume against the Job Description.

STRICT RULES:
1. ATS Score must be an integer between 0 and 100 reflecting the actual skill match.
2. If a required skill is absent from the resume, list it under missing_skills.
3. Keep the output strictly in valid JSON format.

Candidate Resume:
{resume_text[:2500]}

Job Description:
{jd_text[:2000]}

Format JSON response exactly as:
{{
  "ats_score": 80,
  "jd_summary": "Summary of role and core requirements",
  "matching_skills": ["Python", "FastAPI"],
  "missing_skills": ["Kubernetes"]
}}
"""

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=800,
    )
    
    content = response.choices[0].message.content
    data = _extract_json_from_text(content)
    
    score = data.get("ats_score", 50)
    try:
        score = int(score)
    except Exception:
        score = 50
    score = max(0, min(100, score))
    
    return {
        "ats_score": score,
        "jd_summary": data.get("jd_summary", "Role evaluation completed."),
        "matching_skills": data.get("matching_skills", []),
        "missing_skills": data.get("missing_skills", []),
    }


def tailor_resume_safely(client: Groq, resume_text: str, jd_text: str, matching_skills: list, missing_skills: list) -> str:
    """
    Tailor resume strictly within honesty bounds:
    - Reorders sections or rephrases bullet points to emphasize TRUE matching skills.
    - NEVER invents companies, degrees, dates, or skills the candidate does not have.
    - Keeps standard 1-page equivalent length.
    """
    prompt = f"""You are a professional resume strategist.
Optimize the candidate's resume for the target job description.

CRITICAL HARD CONSTRAINTS:
1. ZERO FABRICATION: Do NOT invent experience, job titles, achievements, companies, metrics, or technologies.
2. Only highlight and rephrase TRUE experiences that already exist in the candidate's resume.
3. Naturally weave in JD terminology only where it genuinely reflects what the candidate already did.
4. Keep the output clean, structured plain text with clear section headers.
5. Length must stay approximately 1 page equivalent.

Candidate Original Resume:
{resume_text[:2500]}

Target Job Description:
{jd_text[:1500]}

Matching Skills: {', '.join(matching_skills) if matching_skills else 'Technical skills in resume'}
Candidate Gaps (DO NOT FABRICATE THESE): {', '.join(missing_skills) if missing_skills else 'None'}

Return the full tailored resume in plain text:"""

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=1500,
    )
    
    return response.choices[0].message.content.strip()


def draft_outreach_email(client: Groq, candidate_name: str, company: str, job_title: str,
                         founder_name: str, matching_skills: list, resume_snippet: str) -> str:
    """
    Draft a high-converting, concise cold email for human review.
    """
    recipient_greeting = f"Hi {founder_name}" if founder_name else f"Hi {company} Team"
    
    prompt = f"""You are an expert at drafting short, compelling, non-pushy cold outreach emails for tech internships.

Candidate Name: {candidate_name}
Company: {company}
Role: {job_title}
Greeting Target: {recipient_greeting}
Top Matching Strengths: {', '.join(matching_skills[:4]) if matching_skills else 'Software & AI Development'}
Candidate Context:
{resume_snippet[:1000]}

Guidelines:
- Subject line must be punchy and clear (e.g. "Quick question regarding {job_title} / {candidate_name}").
- Email body must be under 120 words.
- Specifically mention why the candidate is a strong fit based on genuine matching projects/skills.
- Friendly, professional call-to-action (open to a 10-min chat or review of attached resume/portfolio).
- Format: Include "Subject: ..." on the first line, followed by the email body.

Write the email:"""

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=600,
    )
    
    return response.choices[0].message.content.strip()
