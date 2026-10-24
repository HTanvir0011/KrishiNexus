import { DocsPage } from "../pages/DocsPage";

/** The whitepaper keeps its own section navigation and does not load the 3D views. */
export default function DocsShell() {
  return (
    <div className="mx-auto max-w-[1440px] px-4 pt-8 pb-16 sm:px-6">
      <DocsPage />
    </div>
  );
}
