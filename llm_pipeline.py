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
                         founder_name: str, matching_skills: list, resume_snippet: str,
                         company_context: str = "") -> str:
    """
    Draft a high-converting, concise cold email for human review.
    """
    # FIX 1: Enforce correct spelling of the candidate name
    candidate_name = "Deepanshu Tevathiya"
    phone_number = "+91 9318405317"
    
    recipient_greeting = f"Hi {founder_name}" if founder_name else f"Hi {company} Team"
    
    # FIX 2: Strict email structure + company context
    prompt = f"""Draft a cold outreach email for an internship. Do NOT include any intro or outro text, just the email itself starting with the Subject line.

Candidate Name: {candidate_name}
Role: {job_title}
Company: {company}
Recipient: {recipient_greeting}

Company Context:
{company_context[:1000] if company_context else "No website context available. Please infer generally."}

Candidate Resume:
{resume_snippet[:1000]}

Follow this exact structure:
1. A brief respect-for-time opener.
2. One line: who I am (pursuing B.Tech Data Science) + why I'm interested in AI/ML.
3. A specific reference to what {company} actually does — include 2 concrete, genuine observations about their product/mission derived from the Company Context. Rewrite this in your own plain words (no copy-pasting their marketing taglines or stats).
4. One real credibility point: I have end-to-end deployed AI/ML projects with a live callable endpoint. Reference this generally based on my resume.
5. A low-effort yes/no ask (e.g., "would you be open to a quick chat about this role?").
6. Sign-off formatted EXACTLY as:
Best regards,
{candidate_name}
{phone_number}

Constraints:
- Email must start with "Subject: "
- Under 150 words total.
- Use a maximum of 3 em-dashes (—) in the entire email.
- Do not invent any skills not in the resume."""

    # Retry up to 3 times if LLM returns empty
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0
            )
            result = response.choices[0].message.content.strip()
            if result and len(result) > 50:
                return result
            else:
                print(f"LLM returned too short result: '{result}'")
        except Exception as e:
            print(f"LLM API Error: {e}")
            pass

    # Fallback: return a minimal placeholder so the field is never blank
    return f"Subject: Internship Inquiry: {job_title} - {candidate_name}\n\n{recipient_greeting},\n\nI am writing to express my interest in the {job_title} role at {company}. Please find my resume attached for your review.\n\nBest regards,\n{candidate_name}\n{phone_number}"
