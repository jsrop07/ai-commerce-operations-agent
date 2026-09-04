import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "../src/app/App";
import { routes } from "../src/app/routes";

describe("routes", () => {
  it.each(routes)("renders $path", ({ path, label }) => {
    window.history.replaceState({}, "", path);
    render(<App />);
    expect(screen.getByRole("heading", { level: 1, name: label })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: new RegExp(label.split(" / ")[0]) })).toHaveAttribute("aria-current", "page");
  });

  it("moves between routes with Navigation", () => {
    render(<App />);
    fireEvent.click(screen.getByRole("link", { name: "주문 & 매출" }));
    expect(window.location.pathname).toBe("/orders");
    expect(screen.getByRole("heading", { level: 1, name: "주문 & 매출" })).toBeInTheDocument();
  });
});
