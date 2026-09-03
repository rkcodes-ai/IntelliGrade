import type { ReactNode } from "react";

import { Spinner } from "@/components/ui/spinner";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  className?: string;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  getRowId: (row: T) => string;
  isLoading?: boolean;
  isError?: boolean;
  errorMessage?: string;
  emptyMessage?: string;
  /** Optional trailing "Actions" column, rendered per row. */
  renderActions?: (row: T) => ReactNode;
}

/**
 * Presentational, server-driven table shell (sorting/filtering/pagination
 * all happen server-side via the backend's `Page[T]`/`PageParams` contract
 * — see `types/pagination.ts` — so this component only needs to render
 * whatever page of rows it's given, plus loading/error/empty states).
 */
export function DataTable<T>({
  columns,
  rows,
  getRowId,
  isLoading = false,
  isError = false,
  errorMessage = "Failed to load data.",
  emptyMessage = "No records found.",
  renderActions,
}: DataTableProps<T>) {
  const columnCount = columns.length + (renderActions ? 1 : 0);

  return (
    <Table>
      <TableHeader>
        <TableRow>
          {columns.map((column) => (
            <TableHead key={column.key} className={column.className}>
              {column.header}
            </TableHead>
          ))}
          {renderActions && <TableHead className="text-right">Actions</TableHead>}
        </TableRow>
      </TableHeader>
      <TableBody>
        {isLoading ? (
          <TableRow>
            <TableCell colSpan={columnCount} className="py-10 text-center">
              <div className="flex items-center justify-center gap-2 text-muted-foreground">
                <Spinner className="h-4 w-4" />
                Loading...
              </div>
            </TableCell>
          </TableRow>
        ) : isError ? (
          <TableRow>
            <TableCell colSpan={columnCount} className="py-10 text-center text-destructive">
              {errorMessage}
            </TableCell>
          </TableRow>
        ) : rows.length === 0 ? (
          <TableRow>
            <TableCell colSpan={columnCount} className="py-10 text-center text-muted-foreground">
              {emptyMessage}
            </TableCell>
          </TableRow>
        ) : (
          rows.map((row) => (
            <TableRow key={getRowId(row)}>
              {columns.map((column) => (
                <TableCell key={column.key} className={column.className}>
                  {column.render(row)}
                </TableCell>
              ))}
              {renderActions && (
                <TableCell className="text-right">{renderActions(row)}</TableCell>
              )}
            </TableRow>
          ))
        )}
      </TableBody>
    </Table>
  );
}
