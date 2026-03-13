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
ALT, AST, GGT, Bilirubin, Albumin, Creatinine, eGFR.

If a value is above or below the reference range, add [HIGH] or [LOW] at the end of the line.
If no lab values are found in the document, output exactly: NO_LAB_VALUES_FOUND`;

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

    if (hfToken && hfToken !== 'hf_your_token_here') {
      const messages = [
        {
          role: 'user',
          content: [
            {
              type: 'text',
              text: `${EXTRACTION_PROMPT}\n\nLAB DOCUMENT CONTENT:\n${rawText.slice(0, 8000)}`,
            },
          ],
        },
      ];
      const gemmaResult = await callMedGemma(hfToken, messages);
      if (gemmaResult) {
        extractedText = gemmaResult.trim().slice(0, 4000);
      }
      // If MedGemma is unavailable, extractedText stays as the raw PDF text
    }

    console.log(`[extract-labs] ${filename}: ${extractedText.length} chars (MedGemma ${hfToken ? 'attempted' : 'skipped'})`);
    return NextResponse.json({ extractedText });
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

    const messages = [
      {
        role: 'user',
        content: [
          { type: 'text', text: EXTRACTION_PROMPT },
          {
            type: 'image_url',
            image_url: { url: `data:${mimeType};base64,${base64}` },
          },
        ],
      },
    ];

    const gemmaResult = await callMedGemma(hfToken, messages);
    const extractedText = (gemmaResult ?? '').trim().slice(0, 4000);

    console.log(`[extract-labs] ${filename}: ${extractedText.length} chars from image`);
    return NextResponse.json({ extractedText });
  }

  // ── Unsupported type ──────────────────────────────────────────────────────
  return NextResponse.json(
    { error: `Unsupported file type: ${mimeType}. Please upload a PDF, JPG, or PNG.` },
    { status: 415 }
  );
}
