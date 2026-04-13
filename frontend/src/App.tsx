import { BrowserRouter, Route, Routes } from "react-router-dom";
import Navigation from "./components/Navigation";
import AboutPage from "./pages/AboutPage";
import HomePage from "./pages/HomePage";
import JobDetailPage from "./pages/JobDetailPage";
import JobsPage from "./pages/JobsPage";
import LabelPage from "./pages/LabelPage";
import ResultsPage from "./pages/ResultsPage";
import UploadPage from "./pages/UploadPage";

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen flex flex-col">
        <Navigation />
        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/upload" element={<UploadPage />} />
            <Route path="/jobs" element={<JobsPage />} />
            <Route path="/jobs/:jobId" element={<JobDetailPage />} />
            <Route path="/jobs/:jobId/label" element={<LabelPage />} />
            <Route path="/jobs/:jobId/results" element={<ResultsPage />} />
            <Route path="/about" element={<AboutPage />} />
          </Routes>
        </main>
        <footer className="text-center text-xs text-gray-400 py-3 border-t border-gray-200">
          Built on{" "}
          <a
            href="https://arxiv.org/abs/2306.03151"
            target="_blank"
            rel="noreferrer"
            className="text-brand-600 hover:underline"
          >
            DISCOUNT (Perez, Maji, Sheldon 2023)
          </a>
        </footer>
      </div>
    </BrowserRouter>
  );
}
