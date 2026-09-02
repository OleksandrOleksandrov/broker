import "@/styles/globals.css";
import type { AppProps } from "next/app";
import { ToastContainer } from "@/components/Toast";
import ErrorBoundary from "@/components/ErrorBoundary";

export default function App({ Component, pageProps }: AppProps) {
  return (
    <ErrorBoundary>
      <Component {...pageProps} />
      <ToastContainer />
    </ErrorBoundary>
  );
}
