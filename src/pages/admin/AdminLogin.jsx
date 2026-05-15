import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../hooks/useAuth";

export default function AdminLogin() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const { login, isLoading } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    const result = await login(password);
    if (result.success) {
      navigate("/admin");
    } else {
      setError(result.error);
    }
  };

  return (
    <div className="admin-login">
      <div className="admin-login__card">
        <h1 className="admin-login__title">管理后台</h1>
        <form onSubmit={handleSubmit} className="admin-login__form">
          <div className="admin-login__field">
            <label htmlFor="password" className="admin-login__label">
              管理员密码
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="admin-login__input"
              placeholder="请输入管理员密码"
              autoFocus
              disabled={isLoading}
            />
          </div>
          {error && <div className="admin-login__error">{error}</div>}
          <button type="submit" className="admin-login__button" disabled={isLoading || !password}>
            {isLoading ? "登录中..." : "登录"}
          </button>
        </form>
      </div>
    </div>
  );
}
