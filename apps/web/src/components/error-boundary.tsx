import { AlertTriangle, RotateCcw } from "lucide-react";
import { Component, type ErrorInfo, type ReactNode } from "react";

import { Button } from "./ui/button";
import { Card, CardContent } from "./ui/card";

interface ErrorBoundaryProps {
  children: ReactNode;
  scope: "app" | "evidence";
}

interface ErrorBoundaryState {
  error: Error | null;
}

export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("렌더링 경계에서 예외를 복구했습니다.", error, info.componentStack);
  }

  private reset = () => {
    this.setState({ error: null });
  };

  render() {
    const { children, scope } = this.props;
    const { error } = this.state;
    if (!error) return children;

    const content = (
      <Card>
        <CardContent className="grid min-h-64 place-items-center p-8 text-center">
          <div>
            <AlertTriangle className="mx-auto h-8 w-8 text-amber-400" />
            <p className="mt-3 font-medium">
              {scope === "app"
                ? "화면을 표시하는 중 문제가 발생했습니다."
                : "이 Evidence 탭을 표시하지 못했습니다."}
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              다른 화면은 계속 사용할 수 있습니다. 다시 시도해도 반복되면 실행 Evidence를
              확인하세요.
            </p>
            <Button className="mt-4" variant="outline" onClick={this.reset}>
              <RotateCcw className="mr-1.5 h-4 w-4" />
              다시 시도
            </Button>
          </div>
        </CardContent>
      </Card>
    );

    return scope === "app" ? (
      <main className="grid min-h-screen place-items-center p-6">
        <div className="w-full max-w-2xl">{content}</div>
      </main>
    ) : (
      content
    );
  }
}
