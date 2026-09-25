import { NextRequest, NextResponse } from "next/server";

export const maxDuration = 300; // Allow long-running agent LLM loops

export async function POST(req: NextRequest) {
  try {
    const backendUrl = (process.env.SANCTUM_BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:5050").replace(/\/$/, "");
    const body = await req.text();
    const backendRes = await fetch(`${backendUrl}/api/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body,
      // Node 18+ fetch signal
      signal: AbortSignal.timeout(180000), // 3-minute timeout for local LLMs
    });

    const data = await backendRes.text();
    return new NextResponse(data, {
      status: backendRes.status,
      headers: {
        "Content-Type": backendRes.headers.get("Content-Type") || "application/json",
      },
    });
  } catch (error: any) {
    return NextResponse.json(
      { error: error?.message || "Failed to reach backend" },
      { status: 500 }
    );
  }
}
