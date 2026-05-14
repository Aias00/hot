export default function ErrorState({ message }) {
  return (
    <section className="card empty-state">
      <div>
        <h2>数据加载失败</h2>
        <p>{message}</p>
      </div>
    </section>
  );
}
