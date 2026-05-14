export default function EmptyState({ query }) {
  return (
    <section className="card empty-state">
      <div>
        <h2>没有匹配结果</h2>
        <p>
          {query ? `“${query}” 没有命中任何条目。` : "当前没有可显示的条目。"} 换个关键词试试。
        </p>
      </div>
    </section>
  );
}
