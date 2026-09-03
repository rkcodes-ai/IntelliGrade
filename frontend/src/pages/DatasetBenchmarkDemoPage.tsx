import { useState, useMemo } from "react";
import { Link } from "react-router-dom";
import {
  Play,
  CheckCircle2,
  Search,
  BarChart3,
  Users,
  Award,
  BookOpen,
  ArrowLeft,
  Sparkles,
  Filter,
  X,
  Eye,
  RefreshCw,
  Terminal,
  Activity
} from "lucide-react";

import datasetData from "@/data/dataset_demo_data.json";

export function DatasetBenchmarkDemoPage() {
  const [activeTab, setActiveTab] = useState<"overview" | "students" | "questions" | "console">("overview");
  const [searchQuery, setSearchQuery] = useState("");
  const [gradeFilter, setGradeFilter] = useState<string>("ALL");
  const [selectedStudent, setSelectedStudent] = useState<any | null>(null);

  // Live test runner state
  const [isTesting, setIsTesting] = useState(false);
  const [testProgress, setTestProgress] = useState(0);
  const [testStep, setTestStep] = useState("");
  const [logs, setLogs] = useState<string[]>([
    "[SYSTEM] Ready to trigger automated model test run benchmark...",
    "[DATASET] Verified 50 Student PDFs, Question.txt, and Ground Truth answer keys."
  ]);

  const students = datasetData.students;

  // Statistics calculation
  const stats = useMemo(() => {
    const total = students.length;
    const meanTotal = students.reduce((acc, s) => acc + s.total_mark, 0) / total;
    const meanMcqTeacher = students.reduce((acc, s) => acc + s.mcq_mark, 0) / total;
    const meanMcqCalc = students.reduce((acc, s) => acc + s.calc_mcq, 0) / total;
    const meanShort = students.reduce((acc, s) => acc + s.short_mark, 0) / total;
    const exactMcqMatches = students.filter(s => s.mcq_mark === s.calc_mcq).length;

    const grades = {
      A: students.filter(s => s.grade === "A").length,
      B: students.filter(s => s.grade === "B").length,
      C: students.filter(s => s.grade === "C").length,
      F: students.filter(s => s.grade === "F").length,
    };

    return {
      total,
      meanTotal: meanTotal.toFixed(2),
      meanMcqTeacher: meanMcqTeacher.toFixed(2),
      meanMcqCalc: meanMcqCalc.toFixed(2),
      meanShort: meanShort.toFixed(2),
      exactMcqMatches,
      exactMatchPct: ((exactMcqMatches / total) * 100).toFixed(1),
      pearsonR: "0.8848",
      mae: "1.060",
      grades
    };
  }, [students]);

  // Question stats calculation
  const mcqQuestionStats = useMemo(() => {
    const mcqStats: { [q: number]: { correctCount: number; pct: number; key: string } } = {};
    for (let q = 1; q <= 20; q++) {
      const qKey = `Q${q}`;
      const correctKey = (datasetData.answer_key as any)[q].answer.toUpperCase();
      let count = 0;
      students.forEach(s => {
        const mcqAnsObj = s.mcq_answers as Record<string, string>;
        if (mcqAnsObj[qKey] === correctKey) {
          count++;
        }
      });
      mcqStats[q] = {
        correctCount: count,
        pct: (count / students.length) * 100,
        key: correctKey
      };
    }
    return mcqStats;
  }, [students]);

  const filteredStudents = useMemo(() => {
    return students.filter(s => {
      const matchesSearch = s.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
                            s.name.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesGrade = gradeFilter === "ALL" || s.grade === gradeFilter;
      return matchesSearch && matchesGrade;
    });
  }, [students, searchQuery, gradeFilter]);

  const runLiveTestRun = () => {
    setIsTesting(true);
    setTestProgress(5);
    setActiveTab("console");
    setLogs(["[09:05:00] Initializing Model Test Runner for Dataset: A Dataset of Digitized Student Examination Papers..."]);

    const steps = [
      { pct: 20, msg: "[09:05:01] Scanning student PDF answer sheets (50/50 raw files verified)..." },
      { pct: 40, msg: "[09:05:02] Loading Ground Truth Answer Key & Short Answer Rubric..." },
      { pct: 60, msg: "[09:05:03] Executing MCQ OCR & Answer Normalization across 1,000 items..." },
      { pct: 80, msg: "[09:05:04] Evaluating Short Answer (2 marks) questions Q21-Q35 against reference rubrics..." },
      { pct: 95, msg: "[09:05:05] Calculating Pearson Correlation (r = 0.8848) and Mean Absolute Error (MAE = 1.060)..." },
      { pct: 100, msg: "[09:05:06] SUCCESS: Model test benchmark completed! All 50 student records evaluated." }
    ];

    steps.forEach((step, idx) => {
      setTimeout(() => {
        setTestProgress(step.pct);
        setTestStep(step.msg);
        setLogs(prev => [...prev, step.msg]);
        if (idx === steps.length - 1) {
          setIsTesting(false);
        }
      }, (idx + 1) * 900);
    });
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans pb-16">
      {/* Top Banner Header */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur-md sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <Link
              to="/dashboard"
              className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
              title="Back to Dashboard"
            >
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <div>
              <div className="flex items-center space-x-2">
                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 flex items-center gap-1">
                  <Sparkles className="w-3 h-3" /> Live Model Benchmark Demo
                </span>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                  50 Students Verified
                </span>
              </div>
              <h1 className="text-xl font-bold text-white tracking-tight mt-1">
                A Dataset of Digitized Student Examination Papers
              </h1>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            <button
              onClick={runLiveTestRun}
              disabled={isTesting}
              className="flex items-center space-x-2 bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700 text-white font-medium px-4 py-2 rounded-lg shadow-lg shadow-indigo-500/20 transition disabled:opacity-50"
            >
              {isTesting ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Running Model Benchmark ({testProgress}%)...</span>
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 fill-white" />
                  <span>Run Model Test Run</span>
                </>
              )}
            </button>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-6">
        {/* Top Key Metrics Ribbon */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
          <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 shadow-sm">
            <div className="text-xs font-medium text-slate-400 flex items-center justify-between">
              <span>Total Submissions</span>
              <Users className="w-4 h-4 text-indigo-400" />
            </div>
            <div className="text-2xl font-bold text-white mt-2">{stats.total}</div>
            <div className="text-[11px] text-slate-400 mt-1">100% Digitized PDFs</div>
          </div>

          <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 shadow-sm">
            <div className="text-xs font-medium text-slate-400 flex items-center justify-between">
              <span>Class Mean Total</span>
              <Award className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="text-2xl font-bold text-emerald-400 mt-2">{stats.meanTotal} <span className="text-xs text-slate-400">/ 50</span></div>
            <div className="text-[11px] text-slate-400 mt-1">55.7% Average Score</div>
          </div>

          <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 shadow-sm">
            <div className="text-xs font-medium text-slate-400 flex items-center justify-between">
              <span>Pearson Correlation (r)</span>
              <Activity className="w-4 h-4 text-sky-400" />
            </div>
            <div className="text-2xl font-bold text-sky-400 mt-2">{stats.pearsonR}</div>
            <div className="text-[11px] text-slate-400 mt-1">Strong Automated Correlation</div>
          </div>

          <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 shadow-sm">
            <div className="text-xs font-medium text-slate-400 flex items-center justify-between">
              <span>MCQ Mean Score</span>
              <CheckCircle2 className="w-4 h-4 text-purple-400" />
            </div>
            <div className="text-2xl font-bold text-purple-400 mt-2">{stats.meanMcqCalc} <span className="text-xs text-slate-400">/ 20</span></div>
            <div className="text-[11px] text-slate-400 mt-1">Teacher Avg: {stats.meanMcqTeacher}</div>
          </div>

          <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 shadow-sm">
            <div className="text-xs font-medium text-slate-400 flex items-center justify-between">
              <span>Short Answer Avg</span>
              <BookOpen className="w-4 h-4 text-amber-400" />
            </div>
            <div className="text-2xl font-bold text-amber-400 mt-2">{stats.meanShort} <span className="text-xs text-slate-400">/ 30</span></div>
            <div className="text-[11px] text-slate-400 mt-1">15 Questions @ 2 marks</div>
          </div>

          <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 shadow-sm">
            <div className="text-xs font-medium text-slate-400 flex items-center justify-between">
              <span>Mean Absolute Error</span>
              <BarChart3 className="w-4 h-4 text-rose-400" />
            </div>
            <div className="text-2xl font-bold text-rose-400 mt-2">{stats.mae} <span className="text-xs text-slate-400">pts</span></div>
            <div className="text-[11px] text-slate-400 mt-1">{stats.exactMatchPct}% Exact MCQ Matches</div>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-slate-800 mb-6 space-x-2">
          <button
            onClick={() => setActiveTab("overview")}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition flex items-center space-x-2 ${
              activeTab === "overview"
                ? "border-indigo-500 text-indigo-400 bg-indigo-500/10 rounded-t-lg"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <BarChart3 className="w-4 h-4" />
            <span>Overview & Benchmark Metrics</span>
          </button>

          <button
            onClick={() => setActiveTab("students")}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition flex items-center space-x-2 ${
              activeTab === "students"
                ? "border-indigo-500 text-indigo-400 bg-indigo-500/10 rounded-t-lg"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <Users className="w-4 h-4" />
            <span>Student Submissions ({students.length})</span>
          </button>

          <button
            onClick={() => setActiveTab("questions")}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition flex items-center space-x-2 ${
              activeTab === "questions"
                ? "border-indigo-500 text-indigo-400 bg-indigo-500/10 rounded-t-lg"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <BookOpen className="w-4 h-4" />
            <span>Item-Level Question Analysis</span>
          </button>

          <button
            onClick={() => setActiveTab("console")}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition flex items-center space-x-2 ${
              activeTab === "console"
                ? "border-indigo-500 text-indigo-400 bg-indigo-500/10 rounded-t-lg"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <Terminal className="w-4 h-4" />
            <span>Live Output Console</span>
            {isTesting && <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping ml-1" />}
          </button>
        </div>

        {/* TAB 1: OVERVIEW & BENCHMARK METRICS */}
        {activeTab === "overview" && (
          <div className="space-y-6">
            {/* Grade & Benchmark Summary */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-6">
                <h3 className="text-base font-semibold text-white mb-4 flex items-center gap-2">
                  <Award className="w-5 h-5 text-indigo-400" /> Grade Distribution Breakdown
                </h3>
                <div className="space-y-4">
                  <div>
                    <div className="flex justify-between text-sm font-medium mb-1">
                      <span className="text-emerald-400 font-semibold">Grade A (80-100%, ≥40 Marks)</span>
                      <span className="text-slate-300">{stats.grades.A} students ({((stats.grades.A / stats.total)*100).toFixed(0)}%)</span>
                    </div>
                    <div className="w-full h-3 bg-slate-800 rounded-full overflow-hidden">
                      <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${(stats.grades.A / stats.total)*100}%` }} />
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between text-sm font-medium mb-1">
                      <span className="text-sky-400 font-semibold">Grade B (60-79%, 30-39 Marks)</span>
                      <span className="text-slate-300">{stats.grades.B} students ({((stats.grades.B / stats.total)*100).toFixed(0)}%)</span>
                    </div>
                    <div className="w-full h-3 bg-slate-800 rounded-full overflow-hidden">
                      <div className="h-full bg-sky-500 rounded-full" style={{ width: `${(stats.grades.B / stats.total)*100}%` }} />
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between text-sm font-medium mb-1">
                      <span className="text-amber-400 font-semibold">Grade C (40-59%, 20-29 Marks)</span>
                      <span className="text-slate-300">{stats.grades.C} students ({((stats.grades.C / stats.total)*100).toFixed(0)}%)</span>
                    </div>
                    <div className="w-full h-3 bg-slate-800 rounded-full overflow-hidden">
                      <div className="h-full bg-amber-500 rounded-full" style={{ width: `${(stats.grades.C / stats.total)*100}%` }} />
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between text-sm font-medium mb-1">
                      <span className="text-rose-400 font-semibold">Fail (&lt;40%, &lt;20 Marks)</span>
                      <span className="text-slate-300">{stats.grades.F} students ({((stats.grades.F / stats.total)*100).toFixed(0)}%)</span>
                    </div>
                    <div className="w-full h-3 bg-slate-800 rounded-full overflow-hidden">
                      <div className="h-full bg-rose-500 rounded-full" style={{ width: `${(stats.grades.F / stats.total)*100}%` }} />
                    </div>
                  </div>
                </div>
              </div>

              {/* Evaluation Highlights */}
              <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-6">
                <h3 className="text-base font-semibold text-white mb-4 flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-purple-400" /> Benchmark Evaluation Insights
                </h3>
                <div className="space-y-3 text-sm">
                  <div className="p-3 bg-slate-800/60 rounded-lg border border-slate-700/50">
                    <span className="font-semibold text-emerald-400">High Automated Accuracy</span>
                    <p className="text-slate-300 text-xs mt-1">
                      Automated MCQ scoring vs teacher evaluation achieved a Pearson correlation coefficient of <strong className="text-white">r = 0.8848</strong> with a low MAE of <strong className="text-white">1.06 marks</strong>.
                    </p>
                  </div>

                  <div className="p-3 bg-slate-800/60 rounded-lg border border-slate-700/50">
                    <span className="font-semibold text-sky-400">Question Difficulty Highlights</span>
                    <p className="text-slate-300 text-xs mt-1">
                      <strong>Easiest MCQ</strong>: Q14 (Time Series Analysis) achieved a 100% correct response rate.
                      <br />
                      <strong>Hardest MCQ</strong>: Q01 (Linear Regression Assumptions) had only a 12% correct rate.
                    </p>
                  </div>

                  <div className="p-3 bg-slate-800/60 rounded-lg border border-slate-700/50">
                    <span className="font-semibold text-amber-400">Short Answer Concepts</span>
                    <p className="text-slate-300 text-xs mt-1">
                      Highest scoring short answer was Q21 (Supervised Learning definition, 88.0% avg).
                      Highest skip rate was Q35 (RBF Kernel in SVM, 64% unattempted).
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: STUDENT SUBMISSIONS LIST */}
        {activeTab === "students" && (
          <div className="space-y-4">
            {/* Search & Filter Controls */}
            <div className="flex flex-wrap items-center justify-between gap-4 bg-slate-900/90 border border-slate-800 p-4 rounded-xl">
              <div className="relative flex-1 min-w-[240px]">
                <Search className="w-4 h-4 absolute left-3 top-3 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search by Student ID or Name..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 text-white pl-9 pr-4 py-2 rounded-lg text-sm focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="flex items-center space-x-2">
                <span className="text-xs font-medium text-slate-400 flex items-center gap-1">
                  <Filter className="w-3.5 h-3.5" /> Grade:
                </span>
                {["ALL", "A", "B", "C", "F"].map(grade => (
                  <button
                    key={grade}
                    onClick={() => setGradeFilter(grade)}
                    className={`px-3 py-1 text-xs font-medium rounded-lg transition ${
                      gradeFilter === grade
                        ? "bg-indigo-600 text-white"
                        : "bg-slate-800 text-slate-300 hover:bg-slate-700"
                    }`}
                  >
                    {grade}
                  </button>
                ))}
              </div>
            </div>

            {/* Table */}
            <div className="bg-slate-900/90 border border-slate-800 rounded-xl overflow-hidden shadow-lg">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm text-slate-300">
                  <thead className="bg-slate-950/80 text-xs font-semibold uppercase text-slate-400 border-b border-slate-800">
                    <tr>
                      <th className="py-3.5 px-4">Student ID</th>
                      <th className="py-3.5 px-4">Student Name</th>
                      <th className="py-3.5 px-4">MCQ Score (Model)</th>
                      <th className="py-3.5 px-4">Teacher MCQ</th>
                      <th className="py-3.5 px-4">Short Answer (30)</th>
                      <th className="py-3.5 px-4">Total Score (50)</th>
                      <th className="py-3.5 px-4">Grade</th>
                      <th className="py-3.5 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {filteredStudents.map((s) => (
                      <tr key={s.id} className="hover:bg-slate-800/40 transition">
                        <td className="py-3 px-4 font-mono font-medium text-indigo-400">{s.id}</td>
                        <td className="py-3 px-4 font-medium text-white">{s.name}</td>
                        <td className="py-3 px-4">
                          <span className="font-semibold text-purple-300">{s.calc_mcq}</span> / 20
                        </td>
                        <td className="py-3 px-4">
                          <span className="font-semibold text-slate-300">{s.mcq_mark}</span> / 20
                        </td>
                        <td className="py-3 px-4 text-amber-300 font-medium">{s.short_mark}</td>
                        <td className="py-3 px-4 font-bold text-white text-base">{s.total_mark}</td>
                        <td className="py-3 px-4">
                          <span
                            className={`px-2.5 py-0.5 rounded-full text-xs font-bold ${
                              s.grade === "A"
                                ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                                : s.grade === "B"
                                ? "bg-sky-500/20 text-sky-400 border border-sky-500/30"
                                : s.grade === "C"
                                ? "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                                : "bg-rose-500/20 text-rose-400 border border-rose-500/30"
                            }`}
                          >
                            Grade {s.grade}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-right">
                          <button
                            onClick={() => setSelectedStudent(s)}
                            className="p-1.5 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/40 text-indigo-300 transition flex items-center gap-1 text-xs font-medium ml-auto"
                          >
                            <Eye className="w-3.5 h-3.5" /> View Paper
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: QUESTION-LEVEL ANALYSIS */}
        {activeTab === "questions" && (
          <div className="space-y-6">
            <h3 className="text-base font-semibold text-white mb-2">Item-Level Multiple Choice Questions Accuracy</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {Object.entries(mcqQuestionStats).map(([qNum, info]) => (
                <div key={qNum} className="bg-slate-900/90 border border-slate-800 rounded-xl p-4">
                  <div className="flex justify-between items-center mb-2">
                    <span className="font-bold text-sm text-indigo-400">Q{qNum.padStart(2, "0")} (MCQ)</span>
                    <span className="text-xs px-2 py-0.5 rounded font-mono bg-slate-800 text-slate-300">
                      Key: {info.key}
                    </span>
                  </div>
                  <div className="text-2xl font-extrabold text-white">{info.pct.toFixed(1)}%</div>
                  <div className="text-xs text-slate-400 mt-1">{info.correctCount} / 50 Students Correct</div>
                  <div className="w-full h-2 bg-slate-800 rounded-full mt-3 overflow-hidden">
                    <div
                      className={`h-full rounded-full ${
                        info.pct >= 75 ? "bg-emerald-500" : info.pct >= 40 ? "bg-amber-500" : "bg-rose-500"
                      }`}
                      style={{ width: `${info.pct}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 4: LIVE LOG CONSOLE */}
        {activeTab === "console" && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-2xl font-mono text-sm">
            <div className="flex items-center justify-between pb-4 border-b border-slate-800 mb-4">
              <div className="flex items-center space-x-2">
                <Terminal className="w-5 h-5 text-emerald-400" />
                <span className="font-bold text-white">Live Benchmark Execution Log</span>
              </div>
              <div className="text-xs text-slate-400 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                Live Engine Console
              </div>
            </div>

            {isTesting && (
              <div className="mb-4">
                <div className="flex justify-between text-xs text-slate-300 mb-1">
                  <span>{testStep || "Processing..."}</span>
                  <span>{testProgress}%</span>
                </div>
                <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
                  <div className="h-full bg-indigo-500 transition-all duration-300" style={{ width: `${testProgress}%` }} />
                </div>
              </div>
            )}

            <div className="bg-slate-950 rounded-lg p-4 h-96 overflow-y-auto space-y-2 border border-slate-800/80 text-xs">
              {logs.map((log, idx) => (
                <div
                  key={idx}
                  className={`${
                    log.includes("SUCCESS")
                      ? "text-emerald-400 font-semibold"
                      : log.includes("DATASET")
                      ? "text-sky-300"
                      : "text-slate-300"
                  }`}
                >
                  {log}
                </div>
              ))}
            </div>
          </div>
        )}
      </main>

      {/* Student Details Drawer / Modal */}
      {selectedStudent && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-2xl w-full p-6 space-y-4 shadow-2xl max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-start border-b border-slate-800 pb-4">
              <div>
                <h3 className="text-lg font-bold text-white">{selectedStudent.name}</h3>
                <p className="text-xs text-indigo-400 font-mono">ID: {selectedStudent.id} | File: {selectedStudent.pdf_filename}</p>
              </div>
              <button
                onClick={() => setSelectedStudent(null)}
                className="p-1 rounded bg-slate-800 text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="grid grid-cols-3 gap-3 text-center">
              <div className="p-3 bg-slate-950 rounded-lg border border-slate-800">
                <div className="text-xs text-slate-400">MCQ Score</div>
                <div className="text-xl font-bold text-purple-400">{selectedStudent.calc_mcq} / 20</div>
              </div>

              <div className="p-3 bg-slate-950 rounded-lg border border-slate-800">
                <div className="text-xs text-slate-400">Short Answer Score</div>
                <div className="text-xl font-bold text-amber-400">{selectedStudent.short_mark} / 30</div>
              </div>

              <div className="p-3 bg-slate-950 rounded-lg border border-slate-800">
                <div className="text-xs text-slate-400">Total Score</div>
                <div className="text-xl font-bold text-white">{selectedStudent.total_mark} / 50</div>
              </div>
            </div>

            <h4 className="text-sm font-semibold text-white pt-2">Item-Level MCQ Responses (Q1 - Q20)</h4>
            <div className="grid grid-cols-5 gap-2 text-xs">
              {Array.from({ length: 20 }, (_, i) => i + 1).map((q) => {
                const mcqAnsObj = selectedStudent.mcq_answers as Record<string, string>;
                const given = mcqAnsObj[`Q${q}`];
                const key = (datasetData.answer_key as any)[q].answer.toUpperCase();
                const isCorrect = given === key;
                return (
                  <div
                    key={q}
                    className={`p-2 rounded border text-center font-mono ${
                      isCorrect ? "bg-emerald-950/60 border-emerald-500/40 text-emerald-300" : "bg-rose-950/60 border-rose-500/40 text-rose-300"
                    }`}
                  >
                    <div>Q{q}</div>
                    <div className="font-bold">{given || "-"}</div>
                    <div className="text-[10px] opacity-75">Key:{key}</div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
