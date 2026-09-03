import { useState, type ChangeEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Stethoscope } from "lucide-react";

import { getOCRProviderHealth, listOCRProviders, runOCRBenchmark, updateOCRProvider } from "@/api/ocrProviders";
import { DataTable, type Column } from "@/components/common/DataTable";
import { PageHeader } from "@/components/common/PageHeader";
import { PaginationControls } from "@/components/common/PaginationControls";
import { SearchInput } from "@/components/common/SearchInput";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { useToast } from "@/context/ToastProvider";
import { usePaginatedList } from "@/hooks/usePaginatedList";
import { extractErrorMessage } from "@/lib/errors";
import { useAppSelector } from "@/store";
import type { BenchmarkReport, OCRProvider, OCRProviderUpdate } from "@/types/ocr";

/**
 * Admin-only screen over the small (6-row) global OCR provider catalog.
 * Rows are seeded by migration (no create/delete) — only `is_enabled`/
 * `is_default` are patchable, per `OCRProviderUpdate`. Extended (Module 12)
 * with a per-provider live health check and a cross-provider benchmark run
 * — both are on-demand only (never auto-run for all 6 rows at once), since
 * a health check/benchmark genuinely executes each engine (real compute,
 * real cloud-API calls for credential-gated providers).
 */
export function OCRProviderManagementPage() {
  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);
  const canUpdate = permissions.includes("ocr_providers:update");
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const list = usePaginatedList<OCRProvider>({
    queryKey: "ocr-providers",
    fetcher: (params) => listOCRProviders(params),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: OCRProviderUpdate }) => updateOCRProvider(id, data),
    onSuccess: () => {
      toast("OCR provider updated.", "success");
      void queryClient.invalidateQueries({ queryKey: ["ocr-providers"] });
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const [healthTarget, setHealthTarget] = useState<OCRProvider | null>(null);

  const columns: Column<OCRProvider>[] = [
    { key: "code", header: "Code", render: (row) => row.code },
    { key: "name", header: "Name", render: (row) => row.name },
    {
      key: "enabled",
      header: "Enabled",
      render: (row) => (
        <span className={row.is_enabled ? "text-primary" : "text-muted-foreground"}>
          {row.is_enabled ? "Yes" : "No"}
        </span>
      ),
    },
    {
      key: "implemented",
      header: "Implemented",
      render: (row) => (
        <span className={row.is_implemented ? "text-primary" : "text-muted-foreground"}>
          {row.is_implemented ? "Yes" : "No"}
        </span>
      ),
    },
    {
      key: "default",
      header: "Default",
      render: (row) =>
        row.is_default ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-secondary px-2.5 py-1 text-xs">
            <Check className="h-3 w-3" />
            Default
          </span>
        ) : (
          canUpdate && (
            <Button
              variant="outline"
              size="sm"
              disabled={updateMutation.isPending}
              onClick={() => updateMutation.mutate({ id: row.id, data: { is_default: true } })}
            >
              Set as default
            </Button>
          )
        ),
    },
    {
      key: "health",
      header: "Health",
      render: (row) => (
        <Button variant="outline" size="sm" onClick={() => setHealthTarget(row)}>
          <Stethoscope className="mr-1.5 h-3.5 w-3.5" />
          Check
        </Button>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="OCR Provider Management"
        description="Enable or disable OCR providers, choose the institution-wide default, check live engine health, and benchmark providers against each other."
      />

      <div className="mb-4">
        <SearchInput value={list.search} onChange={list.setSearch} placeholder="Search providers..." />
      </div>

      <DataTable
        columns={columns}
        rows={list.items}
        getRowId={(row) => row.id}
        isLoading={list.isLoading}
        isError={list.isError}
        emptyMessage="No OCR providers found."
        renderActions={
          canUpdate
            ? (row) => (
                <Button
                  variant={row.is_enabled ? "outline" : "default"}
                  size="sm"
                  // Enabling an unimplemented provider 422s server-side — block it in the UI instead.
                  disabled={updateMutation.isPending || (!row.is_enabled && !row.is_implemented)}
                  onClick={() =>
                    updateMutation.mutate({ id: row.id, data: { is_enabled: !row.is_enabled } })
                  }
                >
                  {row.is_enabled ? "Disable" : "Enable"}
                </Button>
              )
            : undefined
        }
      />

      <PaginationControls
        page={list.page}
        pageSize={list.pageSize}
        total={list.total}
        totalPages={list.totalPages}
        onPageChange={list.setPage}
        onPageSizeChange={list.setPageSize}
      />

      <HealthDialog provider={healthTarget} onClose={() => setHealthTarget(null)} />

      {canUpdate && <BenchmarkCard providers={list.items} />}
    </div>
  );
}

function HealthDialog({ provider, onClose }: { provider: OCRProvider | null; onClose: () => void }) {
  const healthQuery = useQuery({
    queryKey: ["ocr-provider-health", provider?.id],
    queryFn: () => getOCRProviderHealth(provider!.id),
    enabled: provider !== null,
  });

  return (
    <Dialog open={provider !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{provider?.name} — Live Health Check</DialogTitle>
        </DialogHeader>
        {healthQuery.isLoading && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Spinner className="h-4 w-4" /> Running a real check against the engine...
          </div>
        )}
        {healthQuery.isError && (
          <p className="text-sm text-destructive">{extractErrorMessage(healthQuery.error)}</p>
        )}
        {healthQuery.data && (
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            <dt className="text-muted-foreground">Installed</dt>
            <dd>
              <BoolBadge value={healthQuery.data.installed} />
            </dd>
            <dt className="text-muted-foreground">Version</dt>
            <dd>{healthQuery.data.version ?? "—"}</dd>
            <dt className="text-muted-foreground">Configured</dt>
            <dd>
              <BoolBadge value={healthQuery.data.configured} />
            </dd>
            <dt className="text-muted-foreground">Authenticated</dt>
            <dd>
              <BoolBadge value={healthQuery.data.authenticated} />
            </dd>
            <dt className="text-muted-foreground">Connectivity</dt>
            <dd>
              <BoolBadge value={healthQuery.data.connectivity} />
            </dd>
            <dt className="text-muted-foreground">Dependencies OK</dt>
            <dd>
              <BoolBadge value={healthQuery.data.dependencies_ok} />
            </dd>
            <dt className="text-muted-foreground">GPU available</dt>
            <dd>
              <BoolBadge value={healthQuery.data.gpu_available} />
            </dd>
            <dt className="text-muted-foreground">Ready</dt>
            <dd>
              <BoolBadge value={healthQuery.data.ready} />
            </dd>
            {healthQuery.data.detail && (
              <>
                <dt className="text-muted-foreground">Detail</dt>
                <dd className="col-span-1 text-xs">{healthQuery.data.detail}</dd>
              </>
            )}
          </dl>
        )}
      </DialogContent>
    </Dialog>
  );
}

function BoolBadge({ value }: { value: boolean | null | undefined }) {
  if (value === null || value === undefined) {
    return <Badge variant="outline">n/a</Badge>;
  }
  return <Badge variant={value ? "success" : "danger"}>{value ? "Yes" : "No"}</Badge>;
}

function BenchmarkCard({ providers }: { providers: OCRProvider[] }) {
  const { toast } = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [referenceText, setReferenceText] = useState("");
  const [report, setReport] = useState<BenchmarkReport | null>(null);

  const benchmarkMutation = useMutation({
    mutationFn: () =>
      runOCRBenchmark({
        file: file!,
        referenceText: referenceText || undefined,
      }),
    onSuccess: (data) => {
      setReport(data);
      toast("Benchmark complete.", "success");
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setFile(event.target.files?.[0] ?? null);
  }

  return (
    <Card className="mt-8">
      <CardHeader>
        <CardTitle>Benchmark Providers</CardTitle>
        <p className="text-sm text-muted-foreground">
          Run one page image through every registered provider and compare confidence, speed, and
          (optionally, if you supply the correct transcription) word/character accuracy.
        </p>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="mb-1 block text-sm font-medium">Page image</label>
            <Input type="file" accept="image/*,.pdf" onChange={handleFileChange} />
          </div>
          <div className="min-w-[240px] flex-1">
            <label className="mb-1 block text-sm font-medium">Reference text (optional)</label>
            <Input
              value={referenceText}
              onChange={(event) => setReferenceText(event.target.value)}
              placeholder="Correct transcription, for accuracy scoring"
            />
          </div>
          <Button
            disabled={!file || benchmarkMutation.isPending}
            onClick={() => benchmarkMutation.mutate()}
          >
            {benchmarkMutation.isPending ? "Running..." : "Run Benchmark"}
          </Button>
        </div>

        {report && (
          <div className="mt-6 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-muted-foreground">
                  <th className="py-2 pr-4">Provider</th>
                  <th className="py-2 pr-4">Status</th>
                  <th className="py-2 pr-4">Confidence</th>
                  <th className="py-2 pr-4">Time (s)</th>
                  <th className="py-2 pr-4">Chars/s</th>
                  <th className="py-2 pr-4">Word acc.</th>
                  <th className="py-2 pr-4">Char acc.</th>
                </tr>
              </thead>
              <tbody>
                {report.results.map((result) => (
                  <tr key={result.provider_code} className="border-b border-border/50">
                    <td className="py-2 pr-4 font-medium">
                      {providers.find((provider) => provider.code === result.provider_code)?.name ??
                        result.provider_code}
                    </td>
                    <td className="py-2 pr-4">
                      <Badge variant={result.success ? "success" : "danger"}>
                        {result.success ? "Success" : (result.error ?? "Failed")}
                      </Badge>
                    </td>
                    <td className="py-2 pr-4">
                      {result.average_confidence !== null ? `${result.average_confidence.toFixed(1)}%` : "—"}
                    </td>
                    <td className="py-2 pr-4">
                      {result.processing_time_seconds !== null
                        ? result.processing_time_seconds.toFixed(2)
                        : "—"}
                    </td>
                    <td className="py-2 pr-4">
                      {result.throughput_chars_per_second !== null
                        ? result.throughput_chars_per_second.toFixed(1)
                        : "—"}
                    </td>
                    <td className="py-2 pr-4">
                      {result.word_accuracy !== null ? `${(result.word_accuracy * 100).toFixed(1)}%` : "—"}
                    </td>
                    <td className="py-2 pr-4">
                      {result.character_accuracy !== null
                        ? `${(result.character_accuracy * 100).toFixed(1)}%`
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
