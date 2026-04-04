const links = ['Customers', 'Machines', 'Parts', 'Workers', 'Shifts']

export default function MasterDataPage() {
  return (
    <div>
      <h2 className="text-lg font-semibold mb-3">Master Data</h2>
      <ul className="list-disc pl-5 space-y-1">
        {links.map((x) => (
          <li key={x}>{x}</li>
        ))}
      </ul>
    </div>
  )
}
