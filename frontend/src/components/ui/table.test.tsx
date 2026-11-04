import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

test("the table parts render a table with a caption, a header, a body and a footer", () => {
  render(
    <Table>
      <TableCaption>Containers</TableCaption>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow>
          <TableCell>web</TableCell>
        </TableRow>
      </TableBody>
      <TableFooter>
        <TableRow>
          <TableCell>1 container</TableCell>
        </TableRow>
      </TableFooter>
    </Table>,
  );

  const table = screen.getByRole("table", { name: "Containers" });
  expect(table).toHaveAttribute("data-slot", "table");
  expect(screen.getByRole("columnheader", { name: "Name" })).toBeInTheDocument();
  expect(screen.getByRole("cell", { name: "web" })).toBeInTheDocument();
  expect(screen.getByText("1 container").closest("tfoot")).toHaveAttribute("data-slot", "table-footer");
});
