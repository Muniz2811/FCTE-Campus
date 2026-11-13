import { Component, type ReactNode } from 'react';
export class AppErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() {
    if (!this.state.failed) return this.props.children;
    return <main className="fatal-error"><h1>Vamos reabrir a conversa?</h1>
      <p>Não foi possível abrir esta tela. Recarregue para tentar novamente.</p>
      <button className="primary-button" onClick={() => location.reload()}>Recarregar aplicativo</button></main>;
  }
}
