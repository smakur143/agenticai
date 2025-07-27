import { NextRequest, NextResponse } from "next/server";

// Store active progress streams in memory
// In production, you'd want to use Redis or similar
const progressStreams = new Map<
  string,
  {
    controller: ReadableStreamDefaultController;
    sessionId: string;
  }
>();

interface ProgressUpdate {
  step: number;
  total: number;
  message: string;
  status: "running" | "completed" | "error";
  details?: string;
}

export async function GET(request: NextRequest) {
  const sessionId = request.nextUrl.searchParams.get("sessionId");

  if (!sessionId) {
    return NextResponse.json({ error: "Session ID required" }, { status: 400 });
  }

  const stream = new ReadableStream({
    start(controller) {
      // Store the controller for this session
      progressStreams.set(sessionId, { controller, sessionId });

      // Send initial connection message
      controller.enqueue(
        `data: ${JSON.stringify({
          step: 0,
          total: 6,
          message: "Connected to progress stream",
          status: "running",
        })}\n\n`
      );
    },
    cancel() {
      // Clean up when client disconnects
      progressStreams.delete(sessionId);
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Headers": "Cache-Control",
    },
  });
}

// Utility function to send progress updates
export function sendProgressUpdate(sessionId: string, update: ProgressUpdate) {
  const stream = progressStreams.get(sessionId);
  if (stream) {
    try {
      stream.controller.enqueue(`data: ${JSON.stringify(update)}\n\n`);

      // If completed or error, close the stream after a short delay
      if (update.status === "completed" || update.status === "error") {
        setTimeout(() => {
          stream.controller.close();
          progressStreams.delete(sessionId);
        }, 1000);
      }
    } catch (error) {
      console.error("Error sending progress update:", error);
      progressStreams.delete(sessionId);
    }
  }
}

// Cleanup function to remove old streams
export function cleanupProgressStream(sessionId: string) {
  const stream = progressStreams.get(sessionId);
  if (stream) {
    try {
      stream.controller.close();
    } catch (error) {
      // Stream might already be closed
    }
    progressStreams.delete(sessionId);
  }
}
