import { NextRequest, NextResponse } from "next/server";
import { exec } from "child_process";
import path from "path";
import fs from "fs";
import os from "os";

// Default root directory: sanctum project root or user's repo root
const DEFAULT_CWD = process.cwd();

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const rawCommand = (body.command || "").trim();
    let clientCwd = (body.cwd || DEFAULT_CWD).trim();

    // Validate current working directory exists, otherwise fallback to DEFAULT_CWD
    if (!fs.existsSync(/*turbopackIgnore: true*/ clientCwd) || !fs.statSync(/*turbopackIgnore: true*/ clientCwd).isDirectory()) {
      clientCwd = DEFAULT_CWD;
    }

    if (!rawCommand) {
      return NextResponse.json({
        stdout: "",
        stderr: "",
        exitCode: 0,
        cwd: clientCwd,
        durationMs: 0,
      });
    }

    // ── Special handling for built-in `cd` commands ──
    if (rawCommand === "cd" || rawCommand.startsWith("cd ")) {
      const targetArg = rawCommand.slice(2).trim();
      let targetPath: string;

      if (!targetArg || targetArg === "~") {
        targetPath = os.homedir();
      } else if (targetArg.startsWith("~/")) {
        targetPath = path.join(os.homedir(), targetArg.slice(2));
      } else {
        targetPath = path.resolve(clientCwd, targetArg);
      }

      if (fs.existsSync(/*turbopackIgnore: true*/ targetPath) && fs.statSync(/*turbopackIgnore: true*/ targetPath).isDirectory()) {
        return NextResponse.json({
          stdout: "",
          stderr: "",
          exitCode: 0,
          cwd: targetPath,
          durationMs: 2,
        });
      } else {
        return NextResponse.json({
          stdout: "",
          stderr: `cd: no such file or directory: ${targetArg}\n`,
          exitCode: 1,
          cwd: clientCwd,
          durationMs: 2,
        });
      }
    }

    // ── Execute standard shell command ──
    const startTime = Date.now();

    // Ensure common macOS binary paths are present in PATH
    const systemPaths = [
      "/opt/homebrew/bin",
      "/opt/homebrew/sbin",
      "/usr/local/bin",
      "/usr/bin",
      "/bin",
      "/usr/sbin",
      "/sbin",
    ].join(":");

    const env = {
      ...process.env,
      PATH: process.env.PATH ? `${systemPaths}:${process.env.PATH}` : systemPaths,
      TERM: "xterm-256color",
      FORCE_COLOR: "1",
    };

    const result = await new Promise<{ stdout: string; stderr: string; exitCode: number }>(
      (resolve) => {
        exec(
          rawCommand,
          {
            cwd: clientCwd,
            env,
            timeout: 20000, // 20s timeout limit
            maxBuffer: 1024 * 1024 * 4, // 4MB buffer
            shell: process.platform === "win32" ? "cmd.exe" : "/bin/zsh",
          },
          (error, stdout, stderr) => {
            const exitCode = error ? (typeof error.code === "number" ? error.code : 1) : 0;
            resolve({
              stdout: stdout || "",
              stderr: stderr || (error && !stderr ? error.message : ""),
              exitCode,
            });
          }
        );
      }
    );

    const durationMs = Date.now() - startTime;

    return NextResponse.json({
      stdout: result.stdout,
      stderr: result.stderr,
      exitCode: result.exitCode,
      cwd: clientCwd,
      durationMs,
    });
  } catch (err: any) {
    return NextResponse.json(
      {
        stdout: "",
        stderr: err?.message || "Internal terminal execution error",
        exitCode: 1,
        cwd: DEFAULT_CWD,
        durationMs: 0,
      },
      { status: 500 }
    );
  }
}
