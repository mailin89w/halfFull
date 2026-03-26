"""
Generate HalfFull_Data_Flow.pdf using ReportLab.
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)
from reportlab.lib.enums import TA_LEFT

OUTPUT = "/Users/annaesakova/aipm/halfFull/HalfFull_Data_Flow.pdf"

CONTENT_W = 170 * mm   # 210mm - 20mm - 20mm margins

NAVY   = colors.HexColor("#14376E")
BLUE   = colors.HexColor("#1E5096")
LTBLUE = colors.HexColor("#E8F0FF")
AMBER  = colors.HexColor("#FFF3CD")
AMBR_B = colors.HexColor("#E6B400")
CODE_BG= colors.HexColor("#F0F0F0")
DGREY  = colors.HexColor("#555555")

# ── Styles ───────────────────────────────────────────────────────────────────

def make_styles():
    def s(name, font, size, color=colors.black, leading=None, spaceBefore=0,
          spaceAfter=4, leftIndent=0, firstLineIndent=0):
        return ParagraphStyle(name, fontName=font, fontSize=size,
                              textColor=color, leading=leading or size*1.4,
                              spaceBefore=spaceBefore, spaceAfter=spaceAfter,
                              leftIndent=leftIndent, firstLineIndent=firstLineIndent)
    return {
        "h1":     s("h1",  "Helvetica-Bold", 13, BLUE,         spaceBefore=12, spaceAfter=3),
        "h2":     s("h2",  "Helvetica-Bold", 11, DGREY,        spaceBefore=7,  spaceAfter=3),
        "body":   s("body","Helvetica",       10, colors.black, spaceAfter=5),
        "bullet": s("blt", "Helvetica",       10, colors.black,
                    leftIndent=14, firstLineIndent=-10, spaceAfter=3),
        "code":   s("code","Courier",          9, colors.HexColor("#222222"),
                    leading=13, spaceAfter=0),
        "fpath":  s("fp",  "Courier-Bold",     9, BLUE,         spaceAfter=4),
        "note":   s("nt",  "Helvetica",        9, colors.HexColor("#785000"), spaceAfter=2),
        "noteb":  s("ntb", "Helvetica-Bold",  10, colors.HexColor("#785000"), spaceAfter=3),
        "cover_title":   s("ct", "Helvetica-Bold", 22, colors.white, leading=30),
        "cover_sub":     s("cs", "Helvetica-Bold", 14, colors.HexColor("#A0C8FF"), leading=22),
        "cover_tagline": s("ctl","Helvetica",       10, colors.HexColor("#C8DCFF"), leading=16),
    }

# ── Helpers ──────────────────────────────────────────────────────────────────

def section(text, s, story):
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph(text, s["h1"]))
    story.append(HRFlowable(width=CONTENT_W, thickness=0.8, color=BLUE, spaceAfter=4))

def sub(text, s, story):
    story.append(Paragraph(text, s["h2"]))

def body(text, s, story):
    story.append(Paragraph(text, s["body"]))

def blt(text, s, story):
    story.append(Paragraph(f"\u2022\u00a0\u00a0{text}", s["bullet"]))

def fpath(text, s, story):
    story.append(Paragraph(text, s["fpath"]))

def code_box(lines, s, story):
    rows = [[Paragraph(ln or "\u00a0", s["code"])] for ln in lines]
    t = Table(rows, colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), CODE_BG),
        ("BOX",          (0,0),(-1,-1), 0.5, colors.HexColor("#CCCCCC")),
        ("LEFTPADDING",  (0,0),(-1,-1), 6),
        ("RIGHTPADDING", (0,0),(-1,-1), 6),
        ("TOPPADDING",   (0,0),(0,0),   5),
        ("BOTTOMPADDING",(0,0),(-1,-1), 5),
    ]))
    story.append(t)
    story.append(Spacer(1, 3*mm))

def preprocess_table(s, story):
    hs = ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=9,
                        textColor=colors.white, leading=12)
    cs = ParagraphStyle("tc", fontName="Courier", fontSize=8,
                        leading=11, textColor=colors.HexColor("#222222"))

    col_w = [38*mm, 67*mm, 65*mm]
    headers = ["Input key", "Input value", "Output fields"]
    rows = [
        ('"height_weight"',
         '{"height_cm": "165", "weight_kg": "62"}',
         'height_cm=165, weight_kg=62, bmi=22.8'),
        ('"sleep_hours"',
         '{"sld012___...": "7", "sld013___...": "8"}',
         'sld012___...=7, sld013___...=8'),
        ('"free_time_activity"',
         '{"paq665___...":"1","paq650___...":"2",\n"pad680___...":"240"}',
         'paq665___...=1, paq650___...=2,\npad680___...=240'),
        ('"symptoms_physical"',
         '{"kiq026___...":"2","cdq010___...":"1",\n"mcq520___...":"2"}',
         'kiq026___...=2, cdq010___...=1,\nmcq520___...=2'),
        ('"conditions_diagnosed"',
         '["bpq020___...", "diq010___..."]',
         'All 16 condition fields →\nbpq020___...=1, diq010___...=1,\nmcq010___...=2, ...\n(1=yes, 2=no)'),
        ('"lab_upload"',
         '{structuredValues:\n {total_cholesterol_mg_dl: 195}}',
         'total_cholesterol_mg_dl=195\n(only if not manually entered)'),
        ('"dpq040"', '"3"', 'dpq040=3  (string → int)'),
    ]

    data = [[Paragraph(h, hs) for h in headers]]
    for i, row in enumerate(rows):
        bg = colors.white if i % 2 == 0 else LTBLUE
        data.append([Paragraph(cell.replace("\n","<br/>"), cs) for cell in row])

    t = Table(data, colWidths=col_w, repeatRows=1)
    style = [
        ("BACKGROUND",   (0,0),(-1,0), NAVY),
        ("GRID",         (0,0),(-1,-1), 0.4, colors.HexColor("#CCCCCC")),
        ("VALIGN",       (0,0),(-1,-1), "TOP"),
        ("LEFTPADDING",  (0,0),(-1,-1), 5),
        ("RIGHTPADDING", (0,0),(-1,-1), 5),
        ("TOPPADDING",   (0,0),(-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-1), 4),
    ]
    for i in range(len(rows)):
        bg = colors.white if i % 2 == 0 else LTBLUE
        style.append(("BACKGROUND", (0, i+1), (-1, i+1), bg))
    t.setStyle(TableStyle(style))
    story.append(t)
    story.append(Spacer(1, 3*mm))

def note_box(title, text, s, story):
    inner_s = ParagraphStyle("ni", fontName="Helvetica", fontSize=9.5,
                             textColor=colors.HexColor("#785000"), leading=14)
    title_s = ParagraphStyle("nt", fontName="Helvetica-Bold", fontSize=10,
                             textColor=colors.HexColor("#785000"), leading=15)
    t = Table(
        [[Paragraph(f"\u26a0  {title}", title_s)],
         [Paragraph(text, inner_s)]],
        colWidths=[CONTENT_W - 16*mm]
    )
    outer = Table([[t]], colWidths=[CONTENT_W])
    outer.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), AMBER),
        ("BOX",          (0,0),(-1,-1), 1.0, AMBR_B),
        ("LEFTPADDING",  (0,0),(-1,-1), 8),
        ("RIGHTPADDING", (0,0),(-1,-1), 8),
        ("TOPPADDING",   (0,0),(-1,-1), 6),
        ("BOTTOMPADDING",(0,0),(-1,-1), 6),
    ]))
    story.append(outer)

def cover(s, story):
    t = Table(
        [[Paragraph("HalfFull \u2014 Data Flow", s["cover_title"])],
         [Paragraph("From User Input to Model Score", s["cover_sub"])],
         [Paragraph("How quiz answers travel through all layers of the system", s["cover_tagline"])]],
        colWidths=[CONTENT_W]
    )
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), NAVY),
        ("LEFTPADDING",  (0,0),(-1,-1), 12),
        ("RIGHTPADDING", (0,0),(-1,-1), 12),
        ("TOPPADDING",   (0,0),(0,0),   12),
        ("TOPPADDING",   (0,1),(-1,1),  2),
        ("TOPPADDING",   (0,2),(-1,2),  2),
        ("BOTTOMPADDING",(0,2),(-1,-1), 12),
        ("BOTTOMPADDING",(0,0),(0,0),   2),
        ("BOTTOMPADDING",(0,1),(0,1),   2),
    ]))
    story.append(t)
    story.append(Spacer(1, 6*mm))

# ── Build ────────────────────────────────────────────────────────────────────

def build():
    doc = SimpleDocTemplate(
        OUTPUT, pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=18*mm, bottomMargin=18*mm,
        title="HalfFull Data Flow",
    )
    s = make_styles()
    story = []

    cover(s, story)

    # Section 1
    section("Section 1 \u2014 Overview", s, story)
    body("There are <b>two parallel pipelines</b> that consume the same quiz answers:", s, story)
    blt("<b>AI narrative pipeline:</b> answers \u2192 formatted text \u2192 MedGemma / Claude \u2192 written report", s, story)
    blt("<b>ML scoring pipeline:</b> answers \u2192 flat NHANES numerics \u2192 11 disease models \u2192 risk scores", s, story)

    # Section 2
    section("Section 2 \u2014 Step 1: User Answers a Question", s, story)
    fpath("\u25b6  frontend/src/hooks/useAssessment.ts", s, story)
    body("The quiz page calls <font name='Courier'>setAnswer(questionId, value)</font> on every input. "
         "All answers are stored as one flat object in localStorage "
         "(key: <font name='Courier'>halffull_assessment_v2</font>).", s, story)
    sub("Answer shapes by question type", s, story)
    blt('<font name="Courier">ordinal / categorical / binary</font> \u2014 plain string, e.g. <font name="Courier">"dpq040": "3"</font>', s, story)
    blt('<font name="Courier">dual_numeric</font> \u2014 nested dict, e.g. <font name="Courier">"height_weight": {"height_cm": "165", "weight_kg": "62"}</font>', s, story)
    blt('<font name="Courier">multi_select</font> \u2014 array of selected IDs, e.g. <font name="Courier">"conditions_diagnosed": ["bpq020___...", ...]</font>', s, story)
    blt('<font name="Courier">file_upload</font> \u2014 object with filename + structuredValues from MedGemma extraction', s, story)
    body('<font name="Courier">resolveQuestionPath(answers)</font> re-runs on every change and filters which questions to show. '
         'Conditionals (including <font name="Courier">lab_not_extracted</font>) prune questions already covered by uploaded lab data. '
         'Compound-nested values are looked up recursively so follow-up questions still trigger correctly.', s, story)

    # Section 3
    section("Section 3 \u2014 Step 2: Quiz Completes \u2192 AI Text Prompt", s, story)
    fpath("\u25b6  frontend/src/lib/formatAnswers.ts", s, story)
    body("Destination: <font name='Courier'>/api/generate-followup</font>  and  <font name='Courier'>/api/deep-analyze</font>", s, story)
    body("When the quiz is complete, <font name='Courier'>formatAnswersV2(answers)</font> builds a human-readable text block "
         "for Claude / MedGemma. Compound types are flattened first:", s, story)
    blt('<font name="Courier">height_weight</font> \u2192 "Height: 165 cm, Weight: 62 kg, BMI: 22.8"', s, story)
    blt('<font name="Courier">sleep_hours / free_time_activity / symptoms_physical</font> \u2192 individual field lines', s, story)
    blt('<font name="Courier">conditions_diagnosed</font> array \u2192 readable condition names', s, story)
    blt('<font name="Courier">lab_upload</font> \u2192 structured values as "Total cholesterol: 195 mg/dL" or raw extracted text', s, story)
    sub("Example output sent to AI", s, story)
    code_box([
        "How fatigued do you feel?: Most of the time",
        "Height: 165 cm, Weight: 62 kg, BMI: 22.8",
        "Sleep (weeknights): 7 hrs",
        "Moderate recreational activity: Yes",
        "Diagnosed conditions: High blood pressure, Diabetes",
        "Total cholesterol: 195 mg/dL",
    ], s, story)
    body("This string is read by Claude / MedGemma to write the narrative report, follow-up questions, "
         "doctor recommendations, and coaching tips.", s, story)

    # Section 4
    section("Section 4 \u2014 Step 3: ML Scoring via score_answers.py", s, story)
    fpath("\u25b6  scripts/score_answers.py  (invoked via stdin/stdout pipe from /api/score)", s, story)
    body("The raw answers dict is JSON-serialized and piped in. "
         "The script runs three steps:", s, story)

    sub("Step 3A \u2014 _preprocess(answers): Flatten to numeric NHANES fields", s, story)
    body("Iterates over each answer key and applies type-specific unpacking, "
         "producing a flat dict of numeric NHANES codes:", s, story)
    preprocess_table(s, story)
    body("After flattening, <font name='Courier'>alq111</font> (ever drank alcohol) is derived: "
         "<font name='Courier'>alq111 = 2</font> (never) when avg drinks = 0 AND heavy drinking = no, "
         "else <font name='Courier'>alq111 = 1</font>.", s, story)

    sub("Step 3B \u2014 build_feature_vectors(flat_dict)", s, story)
    fpath("\u25b6  models/questionnaire_to_model_features.py", s, story)
    body("Maps the flat NHANES dict \u2192 one feature vector per model, filling missing values "
         "with model-specific defaults or training-set medians.", s, story)

    sub("Step 3C \u2014 ModelRunner.run_all(feature_vectors)", s, story)
    fpath("\u25b6  models/model_runner.py", s, story)
    body("Loads 11 <font name='Courier'>.joblib</font> model files, runs "
         "<font name='Courier'>predict_proba()</font>, returns positive-class probability:", s, story)
    code_box(['{ "anemia": 0.31, "thyroid": 0.55, "vitamin_d": 0.72, ... }'], s, story)

    # Section 5
    section("Section 5 \u2014 Step 4: Results Page", s, story)
    fpath("\u25b6  frontend/app/results/page.tsx", s, story)
    body("The scores dict and AI narrative are combined on <font name='Courier'>/results</font>:", s, story)
    blt("Risk score bars for each of the 11 conditions", s, story)
    blt("AI-written narrative summary", s, story)
    blt("Doctor specialty recommendations with urgency levels", s, story)
    blt("Suggested additional tests", s, story)
    blt("Doctor visit preparation kit", s, story)
    blt("Lifestyle coaching tips", s, story)

    # Section 6
    section("Section 6 \u2014 Key Architectural Note: Two Separate Unpackers", s, story)
    body("Each compound question type (<font name='Courier'>dual_numeric</font>, "
         "<font name='Courier'>multi_select</font>, <font name='Courier'>file_upload</font>) "
         "must be unpacked in <b>two separate places</b>:", s, story)
    blt("<font name='Courier'>formatAnswers.ts</font> \u2014 for the AI text prompt (human-readable strings)", s, story)
    blt("<font name='Courier'>_preprocess()</font> in <font name='Courier'>score_answers.py</font> "
        "\u2014 for the ML models (numeric NHANES codes)", s, story)
    story.append(Spacer(1, 4*mm))
    note_box(
        "Important",
        "If a new compound question type is added to the quiz, BOTH files must be updated. "
        "Updating only one will silently drop data from one of the two pipelines.",
        s, story
    )

    doc.build(story)
    print(f"Saved: {OUTPUT}")

if __name__ == "__main__":
    build()
