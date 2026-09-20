import React from "react";

import {
  DataComponent,
  DataTable,
  EvidenceChart,
  MetricCard,
  ReportSection,
  RichNarrative,
  useDataApp,
} from "../../data-app-public.jsx";

const chartColors = { people: "var(--chart-1)", value: "var(--chart-2)", evidenceRecords: "var(--chart-3)" };

function EvidenceTable({ id, title, queryId, rows, columns, searchable = false, description }) {
  return <DataComponent id={id} title={title} queryId={queryId} kind="table"
    displayRows={rows} sourceRows={rows} description={description}>
    <DataTable rows={rows} columns={columns} searchable={searchable} compactNumbers={false} label={title} />
  </DataComponent>;
}

export function ReportContent() {
  const { reviewedRows, visible, canEdit, mode, appTitle, setAppTitle } = useDataApp();
  const summaryRows = reviewedRows("summary");
  const [summary] = summaryRows;
  const completeness = reviewedRows("completeness");
  const familyStructure = reviewedRows("family_structure");
  const familySizes = reviewedRows("family_size_distribution");
  const childBirthSpans = reviewedRows("child_birth_span_distribution");
  const parentAges = reviewedRows("parent_age_distribution");
  const longevity = reviewedRows("longevity_distribution");
  const temporal = reviewedRows("temporal");
  const familyNames = reviewedRows("names_and_identity");
  const firstNames = reviewedRows("top_first_names");
  const oldestPeople = reviewedRows("oldest_people");

  return <article className="report-content" aria-label="Genealogy analytics report">
    <header className="report-hero">
      <p className="report-kicker">Combined Muszyna genealogy · DuckDB analytics</p>
      <h1 data-data-app-title contentEditable={canEdit && mode === "edit"} suppressContentEditableWarning
        aria-label={canEdit && mode === "edit" ? "Edit report heading" : undefined}
        onBlur={canEdit && mode === "edit" ? (event) => setAppTitle(event.currentTarget.textContent.trim() || appTitle) : undefined}
        onKeyDown={canEdit && mode === "edit" ? (event) => {
          if (event.key === "Enter") { event.preventDefault(); event.currentTarget.blur(); }
        } : undefined}>{appTitle}</h1>
      <RichNarrative id="report:description" className="report-deck"
        value="A source-backed view of the editable genealogy registries, rebuilt through normalized DuckDB relationship tables. The CSV registries remain the source of truth; this report is the analytical readout." />
    </header>

    {visible("analytics-summary") && <ReportSection id="analytics-summary" title="Executive summary" queryId="summary"
      sourceRows={summaryRows} showHeading={false} className="report-summary">
      <RichNarrative id="analytics-summary:body" className="report-summary-lead" label="Edit executive summary"
        value={`## What the analytical model shows

- **${summary.people} people** appear in **${summary.families} family records**, supported by ${summary.evidenceRecords} evidence records across ${summary.sourceCharts} source charts.
- Normalized relationships produce **${summary.familyChildMemberships} family-child memberships** and **${summary.parentChildEdges} directed parent-child edges**.
- The longest documented acyclic parent-child path reaches **${summary.maximumGeneration} generations**. The registry contains ${summary.components} parent-child components, including isolated people.
- These measures describe the documented registries; missing values are missing observations, not proof that a person, date, partner, or child did not exist.`} />
    </ReportSection>}

    <div className="report-facts" aria-label="Key genealogy analytics">
      {visible("metric-people") && <MetricCard id="metric-people" title="People" queryId="summary" sourceRows={summaryRows}
        value={String(summary.people)} description={`${summary.families} recorded family records.`} />}
      {visible("metric-generation") && <MetricCard id="metric-generation" title="Maximum generation" queryId="summary" sourceRows={summaryRows}
        value={String(summary.maximumGeneration)} description="Longest documented acyclic parent-child path." />}
      {visible("metric-families") && <MetricCard id="metric-families" title="Families" queryId="summary" sourceRows={summaryRows}
        value={String(summary.families)} description="Recorded family or household records." />}
      {visible("metric-sources") && <MetricCard id="metric-sources" title="Source charts" queryId="summary" sourceRows={summaryRows}
        value={String(summary.sourceCharts)} description={`${summary.evidenceRecords} relationship-evidence records.`} />}
    </div>

    <section className="report-section">
      <RichNarrative id="completeness:body" className="report-analysis"
        value="## Dates remain the least complete person-level fields\n\nThe coverage chart uses each measure’s explicit denominator. Family evidence is measured against family records; all other coverage measures use the full person registry." />
      <EvidenceChart id="completeness-chart" queryId="completeness" title="Coverage by field" rows={completeness} sourceRows={completeness} height={390}
        spec={{ type: "horizontalBar", x: "field", y: "coverage_pct", colors: chartColors, valueDecimals: 1, yLabel: "Coverage (%)" }} />
    </section>

    <section className="report-section">
      <RichNarrative id="family:body" className="report-analysis"
        value="## Recorded family structure is useful but incomplete\n\nChildren and partnerships reflect what is documented in the registries. A blank relationship field does not establish that the historical relationship was absent." />
      <EvidenceTable id="family-structure-table" queryId="family_structure" title="Recorded family structure" rows={familyStructure}
        columns={[{ field: "measure", label: "Measure" }, { field: "value", label: "Value" }]} />
      <EvidenceChart id="family-size-chart" queryId="family_size_distribution" title="Distribution of recorded family sizes" rows={familySizes} sourceRows={familySizes} height={310}
        spec={{ type: "bar", x: "family_size", y: "families", colors: chartColors, valueDecimals: 0, distribution: true }} />
      <div className="report-grid">
        <EvidenceChart id="child-birth-span-chart" queryId="child_birth_span_distribution" title="Child birth-year span within a family" rows={childBirthSpans} sourceRows={childBirthSpans} height={310}
          spec={{ type: "bar", x: "span_band", y: "families", colors: chartColors, valueDecimals: 0, distribution: true }} />
        <EvidenceChart id="parent-age-chart" queryId="parent_age_distribution" title="Parent age at a child's recorded birth" rows={parentAges} sourceRows={parentAges} height={310}
          spec={{ type: "bar", x: "age_band", y: "parent_child_observations", colors: chartColors, valueDecimals: 0, distribution: true }} />
      </div>
    </section>

    <section className="report-section">
      <RichNarrative id="longevity:body" className="report-analysis"
        value="## Longevity measures cover only a small dated population\n\nAge at death is calculated only for people with both a recorded birth and death year. That population is small, so this chart describes the dated subset rather than the full genealogy." />
      <EvidenceChart id="longevity-chart" queryId="longevity_distribution" title="Distribution of recorded ages at death" rows={longevity} sourceRows={longevity} height={330}
        spec={{ type: "bar", x: "ageBand", y: "people", colors: chartColors, valueDecimals: 0, distribution: true }} />
    </section>

    <section className="report-section">
      <RichNarrative id="temporal:body" className="report-analysis"
        value="## Recorded births cluster in the early twentieth century\n\nOnly people with an explicit birth year are included. The distribution indicates documentation coverage over time, not the complete historical population." />
      <EvidenceChart id="temporal-chart" queryId="temporal" title="People with recorded births by decade" rows={temporal} sourceRows={temporal} height={340}
        spec={{ type: "bar", x: "decade", y: "people", colors: chartColors, valueDecimals: 0 }} />
    </section>

    <section className="report-section">
      <RichNarrative id="names:body" className="report-analysis"
        value="## Gościński remains the largest normalized family-name group\n\nThe registry’s family-name groups preserve its normalization choices. The chart shows the largest groups; the table retains every group for lookup." />
      <div className="report-grid">
        <EvidenceChart id="family-name-chart" queryId="names_and_identity" title="Largest family-name groups" rows={familyNames.slice(0, 15)} sourceRows={familyNames} height={460}
          spec={{ type: "horizontalBar", x: "familyName", y: "people", colors: chartColors, valueDecimals: 0 }} />
        <EvidenceTable id="family-name-table" queryId="names_and_identity" title="All normalized family-name groups" rows={familyNames} searchable
          columns={[{ field: "familyName", label: "Family-name group" }, { field: "people", label: "People" }]} />
      </div>
    </section>

    <section className="report-section">
      <RichNarrative id="first-names:body" className="report-analysis"
        value="## The most common recorded first names\n\nThis ranking counts each person-registry entry once and preserves the names exactly as recorded." />
      <EvidenceChart id="first-name-chart" queryId="top_first_names" title="Top recorded first names" rows={firstNames} sourceRows={firstNames} height={360}
        spec={{ type: "horizontalBar", x: "firstName", y: "people", colors: chartColors, valueDecimals: 0 }} />
    </section>

    <section className="report-section">
      <RichNarrative id="oldest-people:body" className="report-analysis"
        value="## Oldest people with recorded birth years\n\nThis list contains the ten earliest recorded birth years. It excludes people without a recorded birth year; a recorded year may be approximate where noted." />
      <EvidenceTable id="oldest-people-table" queryId="oldest_people" title="Oldest recorded people" rows={oldestPeople}
        columns={[{ field: "person", label: "Person" }, { field: "birthYear", label: "Birth year" }, { field: "deathYear", label: "Death year" }, { field: "note", label: "Note" }]} />
    </section>
  </article>;
}
