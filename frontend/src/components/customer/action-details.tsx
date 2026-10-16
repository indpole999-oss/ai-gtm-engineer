/** Render the complete saved business payload without exposing transport bindings. */
export function ActionDetails({ value }: { value: unknown }) {
  if (value === null || value === undefined) return <span>Not provided</span>;
  if (Array.isArray(value))
    return (
      <ul className="space-y-2 pl-4">
        {value.map((item, index) => (
          <li key={index}>
            <ActionDetails value={item} />
          </li>
        ))}
      </ul>
    );
  if (typeof value === "object")
    return (
      <dl className="grid gap-3 sm:grid-cols-2">
        {Object.entries(value)
          .filter(([key]) => !["input_hash", "integration_binding"].includes(key))
          .map(([key, item]) => (
            <div key={key} className="min-w-0">
              <dt className="text-xs font-medium capitalize text-muted-foreground">
                {key.replaceAll("_", " ")}
              </dt>
              <dd className="mt-1 break-words text-sm">
                <ActionDetails value={item} />
              </dd>
            </div>
          ))}
      </dl>
    );
  return <span className="whitespace-pre-wrap">{String(value)}</span>;
}
