import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { RefreshCw, Search } from "lucide-react";

import { apiFetch, extractItems, extractTotal } from "@/lib/api";
import { RESOURCE_ENDPOINTS, type ResourceKey } from "@/lib/api-config";
import { deriveColumns, formatValue, humanizeKey, findStatus, rowLabel } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "@/components/state-block";
import { StatusPill } from "@/components/status-pill";

export function useResource(resource: ResourceKey) {
  return useQuery({
    queryKey: ["resource", resource],
    queryFn: () => apiFetch<unknown>(RESOURCE_ENDPOINTS[resource]),
    retry: (failureCount, error) => {
      const status = (error as { status?: number }).status;
      if (status && status < 500) return false;
      return failureCount < 2;
    },
  });
}

interface ResourcePageProps {
  resource: ResourceKey;
  title: string;
  subtitle: string;
}

export function ResourcePage({ resource, title, subtitle }: ResourcePageProps) {
  const query = useResource(resource);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Record<string, unknown> | null>(null);

  const rows = useMemo(() => extractItems(query.data), [query.data]);
  const total = extractTotal(query.data, rows.length);
  const columns = useMemo(() => deriveColumns(rows), [rows]);

  const filtered = useMemo(() => {
    if (!search.trim()) return rows;
    const needle = search.toLowerCase();
    return rows.filter((row) =>
      Object.values(row).some((v) => v !== null && String(v).toLowerCase().includes(needle)),
    );
  }, [rows, search]);

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="label-mono">{RESOURCE_ENDPOINTS[resource]}</p>
          <h1 className="mt-1 text-2xl font-semibold">{title}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={`Filter ${title.toLowerCase()}`}
              className="w-56 pl-9"
              aria-label={`Filter ${title}`}
            />
          </div>
          <Button
            variant="outline"
            size="icon"
            onClick={() => query.refetch()}
            disabled={query.isFetching}
            aria-label="Refresh"
          >
            <RefreshCw className={query.isFetching ? "size-4 animate-spin" : "size-4"} />
          </Button>
        </div>
      </header>

      <div className="overflow-hidden rounded-xl border bg-card">
        {query.isPending ? (
          <LoadingBlock />
        ) : query.isError ? (
          <ErrorBlock error={query.error} resourceLabel={title.toLowerCase()} onRetry={() => query.refetch()} />
        ) : rows.length === 0 ? (
          <EmptyBlock
            title={`No ${title.toLowerCase()} yet`}
            description={`The backend returned an empty list for ${RESOURCE_ENDPOINTS[resource]}.`}
          />
        ) : filtered.length === 0 ? (
          <EmptyBlock title="No matches" description={`Nothing matches "${search}".`} />
        ) : (
          <>
            <div className="flex items-center justify-between border-b px-4 py-2.5">
              <p className="label-mono">
                {filtered.length} of {total} records
              </p>
              {query.isFetching ? <p className="label-mono">Syncing…</p> : null}
            </div>
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    {columns.map((col) => (
                      <TableHead key={col} className="whitespace-nowrap font-mono text-[11px] uppercase tracking-wider">
                        {humanizeKey(col)}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.map((row, i) => {
                    const status = findStatus(row);
                    return (
                      <TableRow
                        key={String(row["id"] ?? i)}
                        onClick={() => setSelected(row)}
                        className="cursor-pointer"
                      >
                        {columns.map((col) => (
                          <TableCell key={col} className="max-w-[22rem] truncate">
                            {status && status.key === col ? (
                              <StatusPill value={row[col]} />
                            ) : (
                              formatValue(col, row[col])
                            )}
                          </TableCell>
                        ))}
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          </>
        )}
      </div>

      <Sheet open={selected !== null} onOpenChange={(open) => !open && setSelected(null)}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
          <SheetHeader>
            <SheetTitle className="font-display">{selected ? rowLabel(selected, "Record") : "Record"}</SheetTitle>
            <SheetDescription>Full record as returned by the backend.</SheetDescription>
          </SheetHeader>
          <dl className="space-y-3 px-4 pb-8">
            {selected
              ? Object.entries(selected).map(([key, value]) => (
                  <div key={key} className="border-b border-border/60 pb-3">
                    <dt className="label-mono">{humanizeKey(key)}</dt>
                    <dd className="mt-1 break-words text-sm">
                      {typeof value === "object" && value !== null ? (
                        <pre className="overflow-x-auto rounded-md bg-muted p-3 font-mono text-xs">
                          {JSON.stringify(value, null, 2)}
                        </pre>
                      ) : (
                        formatValue(key, value)
                      )}
                    </dd>
                  </div>
                ))
              : null}
          </dl>
        </SheetContent>
      </Sheet>
    </div>
  );
}
