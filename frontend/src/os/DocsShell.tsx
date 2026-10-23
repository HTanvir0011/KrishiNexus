import { Backdrop } from "../components/shell/Backdrop";
import { TopBar } from "../components/shell/TopBar";
import { DocsPage } from "../pages/DocsPage";

/** The whitepaper keeps its own section navigation and does not load the 3D views. */
export default function DocsShell() {
  return (
    <div className="relative min-h-screen">
      <Backdrop />
      <div className="relative z-10">
        <TopBar />
        <div className="px-4 pt-6 sm:px-8 lg:px-12">
          <DocsPage />
        </div>
      </div>
    </div>
  );
}
