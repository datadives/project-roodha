import React, { useState, useEffect } from 'react';

export default function AnalyticsPage() {
  const [loading, setLoading] = useState(true);
  const [metrics, setMetrics] = useState({
    activeJobs: 0,
    onTimeDelivery: 0,
    avgLeadTime: 0,
  });
  const [completedJobs, setCompletedJobs] = useState([]);

  useEffect(() => {
    // Simulating the API fetch using your established api_success envelope pattern
    const fetchAnalytics = async () => {
      try {
        // In a real scenario, this would be: await metricsApi.getOwnerDashboard()
        // Mocking the data for the V1.0 presentation
        setTimeout(() => {
          setMetrics({
            activeJobs: 24,
            onTimeDelivery: 92.5,
            avgLeadTime: 4.2, // days
          });
          setCompletedJobs([
            { id: 'JOB-2026-0A1B', customer: 'Alpha Tech', date: '2026-04-03', cost: '₹45,000' },
            { id: 'JOB-2026-9C2D', customer: 'Beta Dynamics', date: '2026-04-02', cost: '₹12,500' },
            { id: 'JOB-2026-3E4F', customer: 'Gamma Corp', date: '2026-04-01', cost: '₹89,000' },
            { id: 'JOB-2026-7G8H', customer: 'Delta Systems', date: '2026-03-30', cost: '₹34,200' },
          ]);
          setLoading(false);
        }, 800); // Slight delay to show the loading state
      } catch (error) {
        console.error("Failed to fetch analytics", error);
        setLoading(false);
      }
    };

    fetchAnalytics();
  }, []);

  const handleExport = () => {
    // Placeholder for V1.5 S3 Pre-signed URL export
    alert("Exporting CSV... (This will trigger the S3 download in V1.5)");
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500 text-lg font-medium animate-pulse">Loading Owner Analytics...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center border-b pb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Owner Analytics</h1>
          <p className="text-sm text-gray-500 mt-1">High-level factory performance and costing.</p>
        </div>
        <button 
          onClick={handleExport}
          className="bg-gray-800 text-white px-4 py-2 rounded-md hover:bg-gray-700 transition shadow-sm text-sm font-medium"
        >
          Export to CSV
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white p-6 rounded-lg shadow border border-gray-100">
          <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wider">Total Active Jobs</h3>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-3xl font-bold text-blue-600">{metrics.activeJobs}</span>
            <span className="text-sm text-gray-500 border-l pl-2 border-gray-200">On Shopfloor</span>
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow border border-gray-100">
          <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wider">On-Time Delivery</h3>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-3xl font-bold text-green-600">{metrics.onTimeDelivery}%</span>
            <span className="text-sm text-green-500 border-l pl-2 border-gray-200">↑ 2.1% this week</span>
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow border border-gray-100">
          <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wider">Avg Lead Time</h3>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-3xl font-bold text-indigo-600">{metrics.avgLeadTime}</span>
            <span className="text-sm text-gray-500 border-l pl-2 border-gray-200">Days per PO</span>
          </div>
        </div>
      </div>

      {/* Completed Jobs Costing Table */}
      <div className="bg-white rounded-lg shadow border border-gray-100 mt-8">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-semibold text-gray-800">Recently Completed Jobs (Costing Preview)</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-gray-50 text-gray-600 text-sm border-b">
                <th className="px-6 py-3 font-medium">Job Number</th>
                <th className="px-6 py-3 font-medium">Customer</th>
                <th className="px-6 py-3 font-medium">Completion Date</th>
                <th className="px-6 py-3 font-medium text-right">Est. Cost (V1.0)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {completedJobs.map((job, index) => (
                <tr key={index} className="hover:bg-gray-50 transition">
                  <td className="px-6 py-4 text-sm font-medium text-gray-900">{job.id}</td>
                  <td className="px-6 py-4 text-sm text-gray-600">{job.customer}</td>
                  <td className="px-6 py-4 text-sm text-gray-600">{job.date}</td>
                  <td className="px-6 py-4 text-sm font-semibold text-gray-900 text-right">{job.cost}</td>
                </tr>
              ))}
              {completedJobs.length === 0 && (
                <tr>
                  <td colSpan="4" className="px-6 py-8 text-center text-gray-500 text-sm">
                    No completed jobs found for this period.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
