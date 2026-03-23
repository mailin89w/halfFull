import { NextRequest, NextResponse } from 'next/server';

const HF_MODEL = 'google/medgemma-1.5-4b-it';
const HF_API_URL = process.env.HF_ENDPOINT_URL
  ? `${process.env.HF_ENDPOINT_URL}/v1/chat/completions`
  : 'https://router.huggingface.co/v1/chat/completions';

const EXTRACTION_PROMPT = `You are a medical AI assistant. Extract all lab test values from the provided document.

For each test found, output one line in this exact format:
TEST NAME: value unit (reference range if shown) [HIGH/LOW if flagged]

Focus especially on these markers if present:
Ferritin, Iron, TIBC, Transferrin saturation, Hemoglobin, MCV, MCH, RBC,
TSH, Free T3, Free T4, Anti-TPO antibodies, Reverse T3,
Vitamin D (25-OH), Vitamin B12, Folate, MMA, Homocysteine,
CRP, ESR, ANA,
Cortisol (morning), DHEA-S, Testosterone,
HbA1c, Fasting glucose, Insulin,
ALT, AST, GGT, Bilirubin, Albumin, Creatinine, eGFR,
Total Cholesterol, HDL, LDL, Triglycerides, Glucose, WBC.

If a value is above or below the reference range, add [HIGH] or [LOW] at the end of the line.
If no lab values are found in the document, output exactly: NO_LAB_VALUES_FOUND`;

const STRUCTURED_PROMPT = `You are a medical data extractor. Given lab report text, output ONLY a JSON object with numeric values for any of these exact keys found in the data (omit keys not present):

{
  "total_cholesterol_mg_dl": <Total Cholesterol in mg/dL>,
  "hdl_cholesterol_mg_dl": <HDL Cholesterol in mg/dL>,
  "ldl_cholesterol_mg_dl": <LDL Cholesterol in mg/dL>,
  "triglycerides_mg_dl": <Triglycerides in mg/dL>,
  "fasting_glucose_mg_dl": <fasting glucose in mg/dL>,
  "glucose_mg_dl": <random/non-fasting glucose in mg/dL>,
  "uacr_mg_g": <urine albumin-to-creatinine ratio in mg/g>,
  "wbc_1000_cells_ul": <WBC count in x10^3 cells/uL>,
  "total_protein_g_dl": <Total Protein in g/dL>
}

Rules:
- Output valid JSON only — no text, no markdown, no units in values.
- Convert units if needed (e.g. mmol/L cholesterol × 38.67 = mg/dL; mmol/L glucose × 18.02 = mg/dL).
- If a value appears as both fasting and non-fasting, use fasting for fasting_glucose_mg_dl.
- Omit any key where the value is unclear or absent.
- If nothing matches, output: {}`;

// ── Regex-based fallback extractor ────────────────────────────────────────────
// Used when MedGemma is unavailable. Parses common lab report patterns like:
//   "Total Cholesterol  188  mg/dL" or "HDL: 54 mg/dL" or "Glucose 94 mg/dL"

const LAB_PATTERNS: Array<{ key: string; pattern: RegExp; toMgDl?: number }> = [
  { key: 'total_cholesterol_mg_dl', pattern: /total\s+cholesterol[^\d]*(\d+(?:\.\d+)?)/i },
  { key: 'hdl_cholesterol_mg_dl',   pattern: /\bhdl(?:\s+cholesterol)?[^\d]*(\d+(?:\.\d+)?)/i },
  { key: 'ldl_cholesterol_mg_dl',   pattern: /\bldl(?:\s+cholesterol)?[^\d]*(\d+(?:\.\d+)?)/i },
  { key: 'triglycerides_mg_dl',     pattern: /triglycerides?[^\d]*(\d+(?:\.\d+)?)/i },
  { key: 'fasting_glucose_mg_dl',   pattern: /(?:fasting\s+(?:blood\s+)?)?glucose[^\d]*(\d+(?:\.\d+)?)/i },
  { key: 'wbc_1000_cells_ul',       pattern: /\bwbc[^\d]*(\d+(?:\.\d+)?)/i },
  { key: 'total_protein_g_dl',      pattern: /total\s+protein[^\d]*(\d+(?:\.\d+)?)/i },
];

function extractStructuredFromText(text: string): Record<string, number> {
  const result: Record<string, number> = {};
  for (const { key, pattern } of LAB_PATTERNS) {
    const match = text.match(pattern);
    if (match) {
      const val = parseFloat(match[1]);
      if (!isNaN(val) && val > 0) result[key] = val;
    }
  }
  return result;
}

/** Call MedGemma and return extracted text, or null if the endpoint is unavailable. */
async function callMedGemma(
  hfToken: string,
  messages: object[]
): Promise<string | null> {
  try {
    const hfResponse = await fetch(HF_API_URL, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${hfToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: HF_MODEL,
        messages,
        max_tokens: 1200,
        temperature: 0.1,
      }),
    });

    if (!hfResponse.ok) {
      console.warn(`[extract-labs] MedGemma returned ${hfResponse.status} — falling back to raw text`);
      return null;
    }

    const data = await hfResponse.json();
    return (data.choices?.[0]?.message?.content as string | undefined) ?? null;
  } catch {
    console.warn('[extract-labs] MedGemma unreachable — falling back to raw text');
    return null;
  }
}

export async function POST(req: NextRequest) {
  const hfToken = process.env.HF_API_TOKEN;

  let body: { filename?: string; base64?: string; mimeType?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  const { filename = 'file', base64 = '', mimeType = 'application/octet-stream' } = body;

  if (!base64) {
    return NextResponse.json({ error: 'No file data provided' }, { status: 400 });
  }

  // ── PDF path ──────────────────────────────────────────────────────────────
  if (mimeType === 'application/pdf') {
    // Step 1: always extract raw text with pdf-parse (works without MedGemma)
    let rawText: string;
    try {
      const { PDFParse } = await import('pdf-parse');
      const buffer = Buffer.from(base64, 'base64');
      const parser = new PDFParse({ data: buffer });
      const pdfData = await parser.getText();
      rawText = pdfData.text.trim();
    } catch (pdfErr) {
      return NextResponse.json(
        { error: `PDF parsing failed: ${String(pdfErr)}` },
        { status: 422 }
      );
    }

    if (!rawText) {
      return NextResponse.json(
        { error: 'No text found in PDF. Try uploading a photo of your results instead.' },
        { status: 422 }
      );
    }

    // Step 2: try MedGemma for structured lab extraction (optional enrichment)
    let extractedText = rawText.slice(0, 4000);
    let structuredValues: Record<string, number> = {};

    if (hfToken && hfToken !== 'hf_your_token_here') {
      // Run both extractions in parallel
      const textMessages = [
        {
          role: 'user',
          content: [{ type: 'text', text: `${EXTRACTION_PROMPT}\n\nLAB DOCUMENT CONTENT:\n${rawText.slice(0, 8000)}` }],
        },
      ];
      const structuredMessages = [
        {
          role: 'user',
          content: [{ type: 'text', text: `${STRUCTURED_PROMPT}\n\nLAB REPORT:\n${rawText.slice(0, 8000)}` }],
        },
      ];
      const [gemmaText, gemmaStructured] = await Promise.all([
        callMedGemma(hfToken, textMessages),
        callMedGemma(hfToken, structuredMessages),
      ]);
      if (gemmaText) extractedText = gemmaText.trim().slice(0, 4000);
      if (gemmaStructured) {
        try {
          const jsonMatch = gemmaStructured.match(/\{[\s\S]*\}/);
          if (jsonMatch) structuredValues = JSON.parse(jsonMatch[0]) as Record<string, number>;
        } catch { /* ignore parse errors */ }
      }
    }

    // Regex fallback: fill any gaps MedGemma missed (or if MedGemma was unavailable)
    const regexValues = extractStructuredFromText(rawText);
    for (const [key, val] of Object.entries(regexValues)) {
      if (!(key in structuredValues)) structuredValues[key] = val;
    }

    console.log(`[extract-labs] ${filename}: ${extractedText.length} chars, ${Object.keys(structuredValues).length} structured values`);
    return NextResponse.json({ extractedText, structuredValues });
  }

  // ── Image path ────────────────────────────────────────────────────────────
  if (mimeType.startsWith('image/')) {
    // Images require MedGemma vision — no server-side text fallback available
    if (!hfToken || hfToken === 'hf_your_token_here') {
      // No MedGemma: still mark upload as done; the image filename is stored
      // and the AI analysis steps will skip structured lab data gracefully.
      console.log(`[extract-labs] ${filename}: MedGemma not configured, storing image reference only`);
      return NextResponse.json({ extractedText: '' });
    }

    const imageContent = { type: 'image_url', image_url: { url: `data:${mimeType};base64,${base64}` } };
    const [gemmaText, gemmaStructured] = await Promise.all([
      callMedGemma(hfToken, [{ role: 'user', content: [{ type: 'text', text: EXTRACTION_PROMPT }, imageContent] }]),
      callMedGemma(hfToken, [{ role: 'user', content: [{ type: 'text', text: STRUCTURED_PROMPT }, imageContent] }]),
    ]);

    const extractedText = (gemmaText ?? '').trim().slice(0, 4000);
    let structuredValues: Record<string, number> = {};
    if (gemmaStructured) {
      try {
        const jsonMatch = gemmaStructured.match(/\{[\s\S]*\}/);
        if (jsonMatch) structuredValues = JSON.parse(jsonMatch[0]) as Record<string, number>;
      } catch { /* ignore parse errors */ }
    }

    console.log(`[extract-labs] ${filename}: ${extractedText.length} chars, ${Object.keys(structuredValues).length} structured values from image`);
    return NextResponse.json({ extractedText, structuredValues });
  }

  // ── Unsupported type ──────────────────────────────────────────────────────
  return NextResponse.json(
    { error: `Unsupported file type: ${mimeType}. Please upload a PDF, JPG, or PNG.` },
    { status: 415 }
  );
}
