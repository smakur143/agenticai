import { NextRequest, NextResponse } from "next/server";
import { spawn } from "child_process";
import path from "path";
import fs from "fs";
import { sendProgressUpdate } from "../progress/route";

interface ScrapingRequest {
  scrapeSite: string;
  productName: string;
  outputFolder: string;
  recipientEmail: string;
}

interface ScrapingProgress {
  step: number;
  total: number;
  message: string;
  status: "running" | "completed" | "error";
  details?: string;
}

class ScrapingOrchestrator {
  private sessionId: string;
  private currentStep = 0;
  private totalSteps = 6;

  constructor(sessionId: string) {
    this.sessionId = sessionId;
  }

  private updateProgress(
    message: string,
    status: "running" | "completed" | "error" = "running",
    details?: string
  ) {
    const progress: ScrapingProgress = {
      step: this.currentStep,
      total: this.totalSteps,
      message,
      status,
      details,
    };

    // Send to progress stream
    sendProgressUpdate(this.sessionId, progress);

    // Also log to console
    console.log(
      `[${this.sessionId}] Step ${this.currentStep}/${this.totalSteps}: ${message}`
    );
  }

  private runPythonScript(
    scriptName: string,
    args: string[] = []
  ): Promise<string> {
    return new Promise((resolve, reject) => {
      const scriptPath = path.join(process.cwd(), "scripts", scriptName);
      const pythonProcess = spawn("python", [scriptPath, ...args], {
        stdio: ["pipe", "pipe", "pipe"],
        shell: true,
      });

      let stdout = "";
      let stderr = "";

      pythonProcess.stdout.on("data", (data) => {
        const output = data.toString();
        stdout += output;
        // Send real-time output as progress details
        this.updateProgress(
          `Running ${scriptName}...`,
          "running",
          output.trim()
        );
      });

      pythonProcess.stderr.on("data", (data) => {
        stderr += data.toString();
      });

      pythonProcess.on("close", (code) => {
        if (code === 0) {
          resolve(stdout);
        } else {
          reject(
            new Error(
              `Script ${scriptName} failed with code ${code}. Error: ${stderr}`
            )
          );
        }
      });

      pythonProcess.on("error", (error) => {
        reject(
          new Error(`Failed to start script ${scriptName}: ${error.message}`)
        );
      });
    });
  }

  async runWorkflow(params: ScrapingRequest): Promise<void> {
    try {
      // Step 1: Product Analysis
      this.currentStep = 1;
      this.updateProgress(
        "Starting product analysis and scraping...",
        "running"
      );
      const site = (params.scrapeSite || "").toLowerCase();
      if (site === "blinkit") {
        // Run Blinkit scraper which can also download images
        await this.runPythonScript("blinkit.py", [
          "--brand",
          params.productName,
          "--out-dir",
          params.outputFolder,
          "--images",
        ]);
      } else {
        // Default to Amazon product analyzer
        await this.runPythonScript("product_analyzer.py", [
          params.scrapeSite,
          params.productName,
          params.outputFolder,
        ]);
      }

      // Step 2: Image Scraping
      this.currentStep = 2;
      if (site === "blinkit") {
        // Blinkit script already downloaded images into product_XXX folders
        this.updateProgress(
          "Blinkit: Product analysis and image scraping completed (steps 1 & 2)",
          "running"
        );
      } else {
        this.updateProgress("Scraping product images...", "running");
        await this.runPythonScript("image_scraper.py", [params.outputFolder]);
      }

      // Step 3: Text Extraction
      this.currentStep = 3;
      this.updateProgress("Extracting text from images using AI...", "running");
      await this.runPythonScript("text_extractor.py", [params.outputFolder]);

      // Step 4: QR Code Detection
      this.currentStep = 4;
      this.updateProgress("Detecting QR codes and barcodes...", "running");
      await this.runPythonScript("qr_orchestrator.py", [params.outputFolder]);

      // Step 5: Data Merging and Credential Check
      this.currentStep = 5;
      this.updateProgress(
        "Merging data and checking credentials...",
        "running"
      );
      await this.runPythonScript("credential_check.py", [params.outputFolder]);

      // Step 6: Email Report
      this.currentStep = 6;
      this.updateProgress("Sending email report...", "running");
      await this.runPythonScript("exception_reporter.py", [
        params.outputFolder,
        params.recipientEmail,
      ]);

      this.updateProgress("All tasks completed successfully!", "completed");
    } catch (error) {
      this.updateProgress(
        `Error: ${error instanceof Error ? error.message : "Unknown error"}`,
        "error"
      );
      throw error;
    }
  }
}

export async function POST(request: NextRequest) {
  try {
    const body: ScrapingRequest = await request.json();

    // Validate required fields
    if (
      !body.scrapeSite ||
      !body.productName ||
      !body.outputFolder ||
      !body.recipientEmail
    ) {
      return NextResponse.json(
        { error: "Missing required fields" },
        { status: 400 }
      );
    }

    // Validate email format
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(body.recipientEmail)) {
      return NextResponse.json(
        { error: "Invalid email format" },
        { status: 400 }
      );
    }

    // Supported sites: Amazon, Blinkit
    const supportedSites = ["amazon", "blinkit"] as const;
    const selectedSite = (body.scrapeSite || "").toLowerCase();
    if (!supportedSites.includes(selectedSite as any)) {
      return NextResponse.json(
        { error: "Supported sites are: Amazon, Blinkit" },
        { status: 400 }
      );
    }

    // Resolve and validate output folder path
    const resolvedOutputFolder = path.resolve(body.outputFolder);

    // Create output folder if it doesn't exist
    if (!fs.existsSync(resolvedOutputFolder)) {
      try {
        fs.mkdirSync(resolvedOutputFolder, { recursive: true });
        console.log(`✅ Created output folder: ${resolvedOutputFolder}`);
      } catch (error) {
        console.error(
          `❌ Failed to create output folder: ${resolvedOutputFolder}`,
          error
        );
        return NextResponse.json(
          {
            error: `Failed to create output folder at "${resolvedOutputFolder}": ${
              error instanceof Error ? error.message : "Unknown error"
            }`,
          },
          { status: 400 }
        );
      }
    } else {
      console.log(`✅ Output folder exists: ${resolvedOutputFolder}`);
    }

    // Generate a unique session ID for progress tracking
    const sessionId = `scrape_${Date.now()}_${Math.random()
      .toString(36)
      .substr(2, 9)}`;

    // Start the scraping workflow in the background
    const orchestrator = new ScrapingOrchestrator(sessionId);

    // Update the body with resolved output folder
    const updatedBody = {
      ...body,
      outputFolder: resolvedOutputFolder,
    };

    // Run workflow asynchronously
    orchestrator.runWorkflow(updatedBody).catch((error) => {
      console.error("Workflow failed:", error);
      // Send error to progress stream
      sendProgressUpdate(sessionId, {
        step: 0,
        total: 6,
        message: `Workflow failed: ${error.message}`,
        status: "error",
      });
    });

    return NextResponse.json({
      success: true,
      sessionId: sessionId,
      message:
        "Scraping workflow started successfully. You will receive an email when complete.",
    });
  } catch (error) {
    console.error("API Error:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
