import { NextRequest, NextResponse } from "next/server";

export const maxDuration = 300;

export async function POST(req: NextRequest) {
  try {
    const backendUrl = (process.env.SANCTUM_BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:5050").replace(/\/$/, "");
    const body = await req.text();
    const backendRes = await fetch(`${backendUrl}/api/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body,
      signal: AbortSignal.timeout(300000),
    });

    if (!backendRes.ok || !backendRes.body) {
      return new NextResponse(backendRes.body, {
        status: backendRes.status,
        headers: { "Content-Type": "text/event-stream" },
      });
    }

    return new NextResponse(backendRes.body, {
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
      },
    });
  } catch (error: any) {
    return NextResponse.json(
      { error: error?.message || "Streaming failed" },
      { status: 500 }
    );
  }
}
