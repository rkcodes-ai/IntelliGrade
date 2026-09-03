import { GraduationCap, Sparkles, Play } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useHealthCheck } from "@/hooks/useHealthCheck";

export function LandingPage() {
  const { data, isLoading, isError } = useHealthCheck();

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-8 p-8 text-center bg-slate-950 text-slate-100 font-sans">
      <div className="flex items-center gap-3">
        <div className="p-3 bg-indigo-600/20 rounded-xl border border-indigo-500/30">
          <GraduationCap className="h-10 w-10 text-indigo-400" />
        </div>
        <h1 className="text-4xl font-extrabold tracking-tight text-white">IntelliGrade AI</h1>
      </div>
      <p className="max-w-xl text-slate-400 text-base leading-relaxed">
        Automated Student Answer Script Evaluation System & OCR Pipeline.
      </p>

      {/* Featured Live Output Demo Card */}
      <div className="w-full max-w-xl bg-gradient-to-br from-indigo-950/60 to-purple-950/60 border border-indigo-500/30 rounded-2xl p-6 shadow-2xl text-left backdrop-blur-md">
        <div className="flex items-center justify-between mb-3">
          <span className="px-3 py-1 rounded-full text-xs font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-indigo-400" /> Live Benchmark Demo Available
          </span>
          <span className="text-xs text-emerald-400 font-mono font-medium">50 Student Papers</span>
        </div>

        <h2 className="text-xl font-bold text-white mb-2">
          A Dataset of Digitized Student Examination Papers
        </h2>
        <p className="text-xs text-slate-300 mb-4">
          Interactive evaluation benchmark featuring ground truth answer keys, 50 student PDFs, itemized MCQ accuracy, short answer scoring, and automated model statistics (Pearson r = 0.8848).
        </p>

        <div className="flex flex-wrap items-center gap-3 pt-2">
          <Button asChild size="lg" className="bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700 text-white font-semibold">
            <Link to="/dataset-demo" className="flex items-center gap-2">
              <Play className="w-4 h-4 fill-white" /> View Live Output Demo
            </Link>
          </Button>

          <Button asChild variant="outline" size="lg" className="border-slate-700 hover:bg-slate-800 text-slate-200">
            <Link to="/login">Sign in to Platform</Link>
          </Button>
        </div>
      </div>

      <Card className="w-full max-w-sm text-left bg-slate-900 border-slate-800 text-slate-300">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm text-white">Backend status</CardTitle>
          <CardDescription className="text-xs text-slate-400">Live connection check from `GET /health`</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading && <p className="text-xs text-slate-400">Checking connection…</p>}
          {isError && (
            <p className="text-xs text-rose-400">
              Offline mode — dataset live demo is available above.
            </p>
          )}
          {data && (
            <p className="text-xs text-emerald-400 font-medium">
              Connected · environment: {data.environment}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
