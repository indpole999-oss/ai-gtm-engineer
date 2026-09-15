import { useMemo, useState, type ReactNode } from "react";
import { ArrowUpDown, Search } from "lucide-react";

import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EmptyBlock } from "@/components/state-block";
import { cn } from "@/lib/utils";

export interface Column<T> {
  key: string;
  header: string;
  render?: (row: T) => ReactNode;
  value?: (row: T) => string | number | null | undefined;
  sortable?: boolean;
  className?: string;
}

interface DataTableProps<T> {
  rows: T[];
  columns: Column<T>[];
  onRowClick?: (row: T) => void;
  searchPlaceholder?: string;
  searchable?: boolean;
  filters?: ReactNode;
  emptyTitle?: string;
  emptyDescription?: string;
  rowKey?: (row: T, index: number) => string;
}

function defaultValue<T>(row: T, key: string): unknown {
  return (row as Record<string, unknown>)[key];
}

export function DataTable<T>({
  rows,
  columns,
  onRowClick,
  searchPlaceholder = "Search",
  searchable = true,
  filters,
  emptyTitle = "No records",
  emptyDescription = "The backend returned an empty list.",
  rowKey,
}: DataTableProps<T>) {
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<{ key: string; dir: "asc" | "desc" } | null>(null);

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) return rows;
    return rows.filter((row) =>
      columns.some((c) => {
        const v = c.value ? c.value(row) : defaultValue(row, c.key);
        return v !== null && v !== undefined && String(v).toLowerCase().includes(needle);
      }),
    );
  }, [rows, search, columns]);

  const sorted = useMemo(() => {
    if (!sort) return filtered;
    const col = columns.find((c) => c.key === sort.key);
    if (!col) return filtered;
    const get = (row: T) => {
      const v = col.value ? col.value(row) : defaultValue(row, col.key);
      return v === null || v === undefined ? "" : v;
    };
    return [...filtered].sort((a, b) => {
      const av = get(a);
      const bv = get(b);
      const cmp =
        typeof av === "number" && typeof bv === "number"
          ? av - bv
          : String(av).localeCompare(String(bv), undefined, { numeric: true });
      return sort.dir === "asc" ? cmp : -cmp;
    });
  }, [filtered, sort, columns]);

  return (
    <div className="space-y-3">
      {(searchable || filters) && (
        <div className="flex flex-wrap items-center gap-2">
          {searchable ? (
            <div className="relative min-w-52 flex-1 sm:max-w-xs">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={searchPlaceholder}
                className="pl-9"
                aria-label={searchPlaceholder}
              />
            </div>
          ) : null}
          {filters}
        </div>
      )}

      <div className="overflow-hidden rounded-lg border bg-card shadow-xs">
        {sorted.length === 0 ? (
          <EmptyBlock
            title={rows.length === 0 ? emptyTitle : "No matches"}
            description={rows.length === 0 ? emptyDescription : `Nothing matches "${search}".`}
          />
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="bg-muted/50">
                  {columns.map((col) => (
                    <TableHead key={col.key} className={cn("whitespace-nowrap", col.className)}>
                      {col.sortable === false ? (
                        col.header
                      ) : (
                        <button
                          type="button"
                          className="inline-flex items-center gap-1 hover:text-foreground"
                          onClick={() =>
                            setSort((prev) =>
                              prev?.key === col.key
                                ? { key: col.key, dir: prev.dir === "asc" ? "desc" : "asc" }
                                : { key: col.key, dir: "asc" },
                            )
                          }
                        >
                          {col.header}
                          <ArrowUpDown
                            className={cn(
                              "size-3",
                              sort?.key === col.key ? "text-foreground" : "text-muted-foreground/60",
                            )}
                            aria-hidden
                          />
                        </button>
                      )}
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {sorted.map((row, i) => (
                  <TableRow
                    key={rowKey ? rowKey(row, i) : String(defaultValue(row, "id") ?? i)}
                    onClick={onRowClick ? () => onRowClick(row) : undefined}
                    className={onRowClick ? "cursor-pointer" : undefined}
                  >
                    {columns.map((col) => (
                      <TableCell key={col.key} className={cn("max-w-[22rem] truncate", col.className)}>
                        {col.render ? col.render(row) : String(defaultValue(row, col.key) ?? "—")}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>

      {sorted.length > 0 ? (
        <p className="text-xs text-muted-foreground">
          Showing {sorted.length} of {rows.length} records from the backend.
        </p>
      ) : null}
    </div>
  );
}
