"""Phase 1: Deterministic filter + Phase 2: AI scoring for all candidates."""
import json, subprocess, asyncio, sys, os
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

BASE = Path("F:/Dropbox/Projects/BEI-ERP/recruitment")
GEMINI_KEY = subprocess.check_output(
    [r"C:\Users\Sam\bin\doppler.exe", "secrets", "get", "GEMINI_API_KEY", "--plain",
     "--project", "bei-erp", "--config", "dev"], text=True
).strip()

# Already interviewed by Ronald (from CFO replacement chat)
ALREADY_INTERVIEWED = {'Jovelynne Tamayo', 'Maria Echevarria', 'Dolores Mejia', 'Eleaser Calayag'}

JOBS = [
    ('head-of-finance-and-accounting-controller', 'Head of Finance and Accounting (Controller)'),
    ('accounting-manager', 'Accounting Manager'),
]

def phase1_filter(candidates, job_type):
    """Deterministic filter using screening question answers."""
    qualified = []
    for c in candidates:
        qa = c.get('questionnaireSubmission', {}).get('result', {}).get('questions', [])

        # Check screening answers
        is_cpa = False
        has_experience = False
        salary_ok = True

        for q in qa:
            answers = [a.get('text', '') for a in q.get('answers', [])]
            status = q.get('status', '')
            q_text = q.get('text', '').lower()

            if 'professional qualification' in q_text or 'cpa' in q_text.lower():
                if any('CPA' in a for a in answers) or any('Certified Public' in a for a in answers):
                    is_cpa = True

            if 'experience' in q_text and ('head' in q_text or 'manager' in q_text or 'accounting role' in q_text):
                if any('5 years' in a or 'More than' in a for a in answers):
                    has_experience = True
                # Also accept 3-4 years for borderline candidates
                if any('3 years' in a or '4 years' in a for a in answers):
                    has_experience = True  # Include but score lower

        # Fit level
        fit = c.get('fitLevelV2', '')

        # Must have: experience in accounting
        # Prefer: CPA, HIGH_FIT
        score = 0
        if is_cpa: score += 20
        if has_experience: score += 15
        if fit == 'HIGH_FIT': score += 10
        elif fit == 'PARTIAL_FIT': score += 3

        # Industry bonus from screening
        for q in qa:
            if 'industry' in q.get('text', '').lower():
                answers = [a.get('text', '') for a in q.get('answers', [])]
                for a in answers:
                    if any(kw in a for kw in ['Food', 'Hospitality', 'Retail', 'Manufacturing']):
                        score += 5
                        break

        # Career tenure bonus
        months = c.get('mostRecentRoleMonths', 0) or 0
        if months >= 60: score += 5  # 5+ years in current role
        elif months >= 36: score += 3

        # Minimum threshold
        if score >= 10:  # At least some qualifications
            full_name = f"{c.get('firstName', '')} {c.get('lastName', '')}".strip()
            qualified.append({
                'name': full_name,
                'pid': c.get('adcentreProspectId', ''),
                'email': c.get('email', ''),
                'phone': c.get('phone', ''),
                'role': c.get('mostRecentJobTitle', ''),
                'company': c.get('mostRecentCompanyName', ''),
                'months': months,
                'fit': fit,
                'is_cpa': is_cpa,
                'has_experience': has_experience,
                'status': c.get('statusFolder', ''),
                'phase1_score': score,
                'location': c.get('profile', {}).get('result', {}).get('homeLocation', {}).get('displayDescription', ''),
                'already_interviewed': full_name in ALREADY_INTERVIEWED,
                'applied': c.get('appliedDateUtc', ''),
            })

    qualified.sort(key=lambda x: x['phase1_score'], reverse=True)
    return qualified


async def phase2_ai_score(candidate, resume_text, job_type):
    """Score candidate using Gemini based on BEI-specific criteria."""
    from google import genai

    client = genai.Client(api_key=GEMINI_KEY)

    prompt = f"""You are evaluating a candidate for the position of {job_type} at Bebang Enterprise Inc. (BEI).

BEI Context:
- QSR franchise (Bebang Halo-Halo) with 47+ stores across Metro Manila
- Currently replacing the CFO who resigned
- Mid-migration to Frappe ERPNext
- Two companies: BEI (retail) + BKI (Bebang Kitchen Inc., commissary/manufacturing)
- Needs someone with STRONG leadership personality (previous CFO lacked executive presence)
- Philippine compliance critical: BIR, SEC, PFRS/PAS

Candidate: {candidate['name']}
Current Role: {candidate['role']} at {candidate['company']}
Time in Role: {candidate['months']//12}y {candidate['months']%12}m
CPA: {'Yes' if candidate['is_cpa'] else 'No'}
Location: {candidate['location']}
SEEK Fit Level: {candidate['fit']}

Resume/Profile:
{resume_text[:4000]}

Score this candidate on each criteria (0-10):
1. LEADERSHIP (executive presence, team management, board/CEO reporting, strategic thinking)
2. QSR_RETAIL (food service, retail chain, franchise, multi-branch experience)
3. MULTI_ENTITY (group consolidation, subsidiaries, intercompany transactions)
4. ERP_SYSTEMS (SAP, Oracle, ERPNext, system implementations)
5. PH_COMPLIANCE (BIR, SEC, PFRS, tax filing, government reporting)
6. CAREER_TRAJECTORY (progression speed, stability, caliber of employers)

Then write a 3-sentence EXECUTIVE SUMMARY focusing on fit for BEI.

Respond in EXACTLY this JSON format:
{{"leadership": N, "qsr_retail": N, "multi_entity": N, "erp_systems": N, "ph_compliance": N, "career_trajectory": N, "total": N, "summary": "3 sentences"}}
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt],
        )
        text = response.text.strip()
        # Extract JSON from response
        if '```' in text:
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]
        result = json.loads(text.strip())
        result['total'] = sum(result.get(k, 0) for k in ['leadership', 'qsr_retail', 'multi_entity', 'erp_systems', 'ph_compliance', 'career_trajectory'])
        return result
    except Exception as e:
        return {'leadership': 0, 'qsr_retail': 0, 'multi_entity': 0, 'erp_systems': 0, 'ph_compliance': 0, 'career_trajectory': 0, 'total': 0, 'summary': f'Error: {e}', 'error': True}


async def process_job(folder, job_type):
    """Process all candidates for a job."""
    job_dir = BASE / folder
    candidates = json.loads((job_dir / 'all_candidates.json').read_text(encoding='utf-8'))

    print(f"\n{'='*70}")
    print(f"  {job_type} ({len(candidates)} total)")
    print(f"{'='*70}")

    # Phase 1: Filter
    print("\nPhase 1: Deterministic filter...")
    qualified = phase1_filter(candidates, job_type)
    print(f"  {len(qualified)} qualified out of {len(candidates)}")

    # Phase 2: AI scoring (only for top candidates by phase1 score)
    # Take top 50 by phase1 score to avoid scoring obviously weak candidates
    top_candidates = qualified[:50]
    print(f"\nPhase 2: AI scoring top {len(top_candidates)} candidates...")

    semaphore = asyncio.Semaphore(8)

    async def score_one(candidate):
        async with semaphore:
            # Load extracted resume text
            safe_name = candidate['name'].replace(' ', '_')
            for ch in list(safe_name):
                if not (ch.isalnum() or ch in '.-_'):
                    safe_name = safe_name.replace(ch, '')
            safe_name = safe_name[:60]

            resume_path = job_dir / 'extracted' / f'{safe_name}.txt'
            if resume_path.exists():
                resume_text = resume_path.read_text(encoding='utf-8')[:4000]
            else:
                # Try profile
                profile_path = job_dir / 'profiles' / f'{safe_name}.md'
                if profile_path.exists():
                    resume_text = profile_path.read_text(encoding='utf-8')[:4000]
                else:
                    resume_text = f"Current: {candidate['role']} at {candidate['company']}"

            ai_scores = await phase2_ai_score(candidate, resume_text, job_type)
            candidate['ai_scores'] = ai_scores
            candidate['final_score'] = candidate['phase1_score'] + ai_scores.get('total', 0)
            return candidate

    tasks = [score_one(c) for c in top_candidates]
    scored = await asyncio.gather(*tasks)

    # Sort by final score
    scored.sort(key=lambda x: x['final_score'], reverse=True)

    # Save full results
    output = {
        'job': job_type,
        'total_candidates': len(candidates),
        'qualified': len(qualified),
        'scored': len(scored),
        'timestamp': datetime.now().isoformat(),
        'rankings': scored,
    }
    (job_dir / 'rankings.json').write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')

    # Print top 15
    print(f"\n{'='*70}")
    print(f"  TOP 15 — {job_type}")
    print(f"{'='*70}")
    for i, c in enumerate(scored[:15]):
        ai = c.get('ai_scores', {})
        flag = " [ALREADY INTERVIEWED]" if c['already_interviewed'] else ""
        cpa = "CPA" if c['is_cpa'] else "---"
        print(f"\n  #{i+1} | {c['name']}{flag}")
        print(f"     {c['role']} at {c['company']} ({c['months']//12}y)")
        print(f"     {cpa} | {c['fit']} | Score: {c['final_score']} (P1:{c['phase1_score']} + AI:{ai.get('total',0)})")
        print(f"     L:{ai.get('leadership',0)} R:{ai.get('qsr_retail',0)} M:{ai.get('multi_entity',0)} E:{ai.get('erp_systems',0)} C:{ai.get('ph_compliance',0)} T:{ai.get('career_trajectory',0)}")
        summary = ai.get('summary', 'N/A')
        if isinstance(summary, str):
            print(f"     {summary[:200]}")

    return scored


async def main():
    all_results = {}
    for folder, job_type in JOBS:
        scored = await process_job(folder, job_type)
        all_results[job_type] = scored

    # Save combined report
    report_path = BASE / 'CANDIDATE_RANKINGS.md'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"# BEI Candidate Rankings\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M PHT')}\n\n")
        f.write(f"## Scoring Criteria\n")
        f.write(f"- **Phase 1 (max 50):** CPA(20) + Experience(15) + Fit(10) + Industry(5) + Tenure(5)\n")
        f.write(f"- **Phase 2 AI (max 60):** Leadership(10) + QSR/Retail(10) + Multi-Entity(10) + ERP(10) + PH Compliance(10) + Career(10)\n")
        f.write(f"- **Total max: 110**\n\n")

        for job_type, scored in all_results.items():
            f.write(f"---\n\n## {job_type}\n\n")
            f.write(f"| # | Name | Current Role | Company | CPA | Fit | Score | Summary |\n")
            f.write(f"|---|------|-------------|---------|-----|-----|-------|--------|\n")
            for i, c in enumerate(scored[:20]):
                ai = c.get('ai_scores', {})
                flag = " *" if c['already_interviewed'] else ""
                cpa = "Yes" if c['is_cpa'] else "No"
                summary = (ai.get('summary', '') or '')[:150].replace('|', '/')
                f.write(f"| {i+1} | **{c['name']}**{flag} | {c['role']} | {c['company']} | {cpa} | {c['fit'] or 'N/A'} | **{c['final_score']}** | {summary} |\n")
            f.write(f"\n\\* = Already interviewed by Ronald\n\n")

    print(f"\n\nFull report: {report_path}")
    print("Rankings JSON saved per job folder.")


if __name__ == '__main__':
    asyncio.run(main())
