import { useEffect, useState } from "react";
import CircularProgressBar from "./components/CircularProgress";

const BASE_URL = import.meta.env.VITE_BACKEND_URL;

interface GenerateReportResponse {
  message: string;
  task_id: string;
}

interface Progress {
  stores_processed: number;
  total_stores: number;
}

interface GetReportResponse extends Progress {
  message: string;
  report_id: string;
}

function App() {
  const [report, setReport] = useState<string | null>(null);
  const [reportGenerationStatus, setReportGenerationStatus] =
    useState<boolean>(false);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [error, setError] = useState<string | null>(null);

  const generateReport = async () => {
    setError(null);
    setReportGenerationStatus(false);
    setProgress(null);
    const resp = await fetch(`${BASE_URL}/reports/trigger_report`, {
      method: "POST",
    });
    const data = (await resp.json()) as GenerateReportResponse;
    setReport(data.task_id);
  };

  useEffect(() => {
    if (!report) return;

    const interval = setInterval(async () => {
      const resp = await fetch(
        `${BASE_URL}/reports/get_report?report_id=${report}`
      );

      if (!resp.ok) {
        setError("Something went wrong");
        clearInterval(interval);
        return;
      }

      if (resp.headers.get("content-type") !== "application/json" && resp.ok) {
        setReportGenerationStatus(true);
        setProgress({
          // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
          stores_processed: progress!.total_stores,
          // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
          total_stores: progress!.total_stores,
        });
        clearInterval(interval);
        return;
      }

      const data = (await resp.json()) as GetReportResponse;
      setProgress({
        stores_processed: data.stores_processed,
        total_stores: data.total_stores,
      });
    }, 1000);

    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [report]);

  return (
    <div>
      <h1>Generate Report</h1>
      <p>Click the button below to generate a report.</p>
      <button onClick={generateReport}>Generate</button>

      {error && <p>{error}</p>}
      {progress && (
        <div>
          <br />

          <CircularProgressBar
            selectedValue={Math.floor(
              (progress.stores_processed / progress.total_stores) * 100
            )}
            maxValue={100}
            textColor="#f00"
            activeStrokeColor="#cc6600"
            withGradient
          />
          <p>
            {progress.stores_processed} stores processed /{" "}
            {progress.total_stores} total stores
          </p>
        </div>
      )}

      {reportGenerationStatus && (
        <div>
          <br />
          <a href={`${BASE_URL}/reports/get_report?report_id=${report}`}>
            Download report
          </a>
        </div>
      )}
    </div>
  );
}

export default App;
