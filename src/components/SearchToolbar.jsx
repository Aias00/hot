export default function SearchToolbar({ query, onQueryChange }) {
  return (
    <form
      className="filter-form"
      onSubmit={(event) => {
        event.preventDefault();
      }}
    >
      <label className="sr-only" htmlFor="query-input">
        搜索标题或摘要
      </label>
      <div className="filter-toolbar">
        <input
          className="field field-grow"
          id="query-input"
          type="search"
          name="query"
          placeholder="搜索标题/摘要..."
          autoComplete="off"
          value={query}
          onChange={(event) => {
            onQueryChange(event.target.value);
          }}
        />
        <button className="btn btn-primary btn-sm" type="submit">
          筛选
        </button>
      </div>
    </form>
  );
}
