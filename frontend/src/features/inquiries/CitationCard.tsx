type CitationItem = {
  source_type: string;
  source_id: string;
  title: string;
  record_or_field: string;
  as_of: string;
  score: number;
};

type CitationCardProps = {
  citation: CitationItem;
  defaultOpen?: boolean;
};

export default function CitationCard({
  citation,
  defaultOpen = false,
}: CitationCardProps) {
  return (
    <details
      className="citation-card"
      open={defaultOpen}
    >
      <summary className="citation-card-summary">
        <span>
          <strong>{citation.title}</strong>
          <span className="tertiary">
            {" "}
            · {citation.source_type}
          </span>
        </span>

        <span className="mono">
          {(citation.score * 100).toFixed(0)}%
        </span>
      </summary>

      <div className="citation-card-body">
        <dl className="citation-fields">
          <div>
            <dt>Source ID</dt>
            <dd className="mono">
              {citation.source_id}
            </dd>
          </div>

          <div>
            <dt>Record / Field</dt>
            <dd>{citation.record_or_field}</dd>
          </div>

          <div>
            <dt>as_of</dt>
            <dd>
              <time dateTime={citation.as_of}>
                {citation.as_of}
              </time>
            </dd>
          </div>

          <div>
            <dt>Score</dt>
            <dd>
              {(citation.score * 100).toFixed(0)}%
            </dd>
          </div>
        </dl>
      </div>
    </details>
  );
}

export type { CitationItem };