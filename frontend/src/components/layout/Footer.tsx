export function Footer() {
  return (
    <footer className="border-t border-border bg-card px-4 py-3 text-center text-xs text-muted-foreground">
      © {new Date().getFullYear()} IntelliGrade. All rights reserved.
    </footer>
  );
}
