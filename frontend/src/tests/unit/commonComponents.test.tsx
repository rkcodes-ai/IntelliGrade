import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { DataTable, type Column } from "@/components/common/DataTable";
import { FormDialog } from "@/components/common/FormDialog";
import { FormField } from "@/components/common/FormField";
import { PageHeader } from "@/components/common/PageHeader";
import { PaginationControls } from "@/components/common/PaginationControls";
import { SearchInput } from "@/components/common/SearchInput";
import { Input } from "@/components/ui/input";

interface Row {
  id: string;
  name: string;
}

const columns: Column<Row>[] = [{ key: "name", header: "Name", render: (row) => row.name }];

describe("DataTable", () => {
  it("shows a loading state", () => {
    render(<DataTable columns={columns} rows={[]} getRowId={(r) => r.id} isLoading />);
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("shows an error state", () => {
    render(
      <DataTable columns={columns} rows={[]} getRowId={(r) => r.id} isError errorMessage="Boom" />,
    );
    expect(screen.getByText("Boom")).toBeInTheDocument();
  });

  it("shows an empty state", () => {
    render(<DataTable columns={columns} rows={[]} getRowId={(r) => r.id} emptyMessage="Nothing here" />);
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
  });

  it("renders rows and an actions column when provided", () => {
    render(
      <DataTable
        columns={columns}
        rows={[{ id: "1", name: "Acme" }]}
        getRowId={(r) => r.id}
        renderActions={(row) => <button>{`Edit ${row.name}`}</button>}
      />,
    );
    expect(screen.getByText("Acme")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Edit Acme" })).toBeInTheDocument();
  });
});

describe("PaginationControls", () => {
  it("disables previous on the first page and next on the last page", () => {
    render(
      <PaginationControls
        page={1}
        pageSize={20}
        total={20}
        totalPages={1}
        onPageChange={vi.fn()}
        onPageSizeChange={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: "Previous page" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next page" })).toBeDisabled();
  });

  it("calls onPageChange when next is clicked", async () => {
    const onPageChange = vi.fn();
    render(
      <PaginationControls
        page={1}
        pageSize={20}
        total={40}
        totalPages={2}
        onPageChange={onPageChange}
        onPageSizeChange={vi.fn()}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Next page" }));
    expect(onPageChange).toHaveBeenCalledWith(2);
  });

  it("calls onPageSizeChange when the page size select changes", async () => {
    const onPageSizeChange = vi.fn();
    render(
      <PaginationControls
        page={1}
        pageSize={20}
        total={40}
        totalPages={2}
        onPageChange={vi.fn()}
        onPageSizeChange={onPageSizeChange}
      />,
    );
    await userEvent.selectOptions(screen.getByLabelText("Rows per page"), "50");
    expect(onPageSizeChange).toHaveBeenCalledWith(50);
  });
});

describe("SearchInput", () => {
  it("debounces onChange after typing stops", async () => {
    vi.useFakeTimers();
    const onChange = vi.fn();
    render(<SearchInput value="" onChange={onChange} debounceMs={300} placeholder="Search..." />);

    const input = screen.getByPlaceholderText("Search...") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "acme" } });

    expect(onChange).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(300);
    expect(onChange).toHaveBeenCalledWith("acme");
    vi.useRealTimers();
  });
});

describe("ConfirmDialog", () => {
  it("calls onConfirm when confirmed", async () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmDialog
        open
        onOpenChange={vi.fn()}
        title="Delete?"
        description="Are you sure?"
        onConfirm={onConfirm}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Confirm" }));
    expect(onConfirm).toHaveBeenCalled();
  });

  it("calls onOpenChange(false) when cancelled", async () => {
    const onOpenChange = vi.fn();
    render(
      <ConfirmDialog
        open
        onOpenChange={onOpenChange}
        title="Delete?"
        description="Are you sure?"
        onConfirm={vi.fn()}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});

describe("FormDialog", () => {
  it("renders children and calls onSubmit", async () => {
    const onSubmit = vi.fn((event: React.FormEvent) => event.preventDefault());
    render(
      <FormDialog open onOpenChange={vi.fn()} title="New Widget" onSubmit={onSubmit}>
        <FormField htmlFor="widget-name" label="Name" required>
          <Input id="widget-name" />
        </FormField>
      </FormDialog>,
    );
    expect(screen.getByLabelText(/Name/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(onSubmit).toHaveBeenCalled();
  });

  it("shows a field error message", () => {
    render(
      <FormDialog open onOpenChange={vi.fn()} title="New Widget" onSubmit={vi.fn()}>
        <FormField htmlFor="widget-name" label="Name" error="Name is required">
          <Input id="widget-name" />
        </FormField>
      </FormDialog>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Name is required");
  });
});

describe("PageHeader", () => {
  it("renders title, description, and actions", () => {
    render(<PageHeader title="Widgets" description="Manage widgets" actions={<button>New</button>} />);
    expect(screen.getByText("Widgets")).toBeInTheDocument();
    expect(screen.getByText("Manage widgets")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "New" })).toBeInTheDocument();
  });
});

function ControlledSearchInput() {
  const [value, setValue] = useState("");
  return <SearchInput value={value} onChange={setValue} />;
}

describe("SearchInput controlled usage", () => {
  it("renders with default placeholder", () => {
    render(<ControlledSearchInput />);
    expect(screen.getByPlaceholderText("Search...")).toBeInTheDocument();
  });
});
