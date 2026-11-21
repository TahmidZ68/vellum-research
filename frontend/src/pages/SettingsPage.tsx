import React, { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Cpu, Globe, Save } from "lucide-react";
import { api } from "@/services/api";
import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";
import { Badge, Button, Card, Input } from "@/components/ui/primitives";

export function SettingsPage() {
  const { refreshUser } = useAuth();
  const { theme, setTheme } = useTheme();
  const queryClient = useQueryClient();

  const settingsQuery = useQuery({
    queryKey: ["settings-overview"],
    queryFn: () => api.getSettings(),
  });

  const [fullName, setFullName] = useState("");
  const [preferredLanguage, setPreferredLanguage] = useState("en");
  const [savedMsg, setSavedMsg] = useState("");

  useEffect(() => {
    if (settingsQuery.data?.user) {
      setFullName(settingsQuery.data.user.full_name || "");
      setPreferredLanguage(settingsQuery.data.user.preferred_language || "en");
    }
  }, [settingsQuery.data]);

  const saveMutation = useMutation({
    mutationFn: () =>
      api.updateSettings({
        full_name: fullName,
        preferred_language: preferredLanguage,
        preferred_theme: theme,
      }),
    onSuccess: async () => {
      setSavedMsg("Preferences saved.");
      await refreshUser();
      await queryClient.invalidateQueries({ queryKey: ["settings-overview"] });
    },
  });

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    setSavedMsg("");
    saveMutation.mutate();
  };

  const overview = settingsQuery.data;

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Settings & Provider Status</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Manage workspace preferences, review backend provider readiness, and inspect daily usage.
        </p>
      </div>

      {/* Account & Theme Preferences */}
      <Card className="p-6">
        <form onSubmit={handleSave} className="space-y-5">
          <h2 className="font-semibold text-base">Account & Display</h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label htmlFor="settings-name" className="text-xs font-medium text-muted-foreground">
                Full name
              </label>
              <Input
                id="settings-name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="settings-lang" className="text-xs font-medium text-muted-foreground">
                Default report language
              </label>
              <select
                id="settings-lang"
                value={preferredLanguage}
                onChange={(e) => setPreferredLanguage(e.target.value)}
                className="flex h-10 w-full rounded-lg border bg-background px-3 py-2 text-sm"
              >
                <option value="en">English</option>
                <option value="bn">Bengali (বাংলা)</option>
              </select>
            </div>
          </div>

          <div className="space-y-2">
            <span className="text-xs font-medium text-muted-foreground block">Interface Theme</span>
            <div className="flex gap-3">
              <Button
                type="button"
                variant={theme === "dark" ? "default" : "outline"}
                size="sm"
                onClick={() => setTheme("dark")}
              >
                Dark Navy
              </Button>
              <Button
                type="button"
                variant={theme === "light" ? "default" : "outline"}
                size="sm"
                onClick={() => setTheme("light")}
              >
                Light
              </Button>
            </div>
          </div>

          <div className="flex items-center justify-between pt-2">
            <span className="text-xs text-emerald-400 flex items-center gap-1.5">
              {savedMsg && (
                <>
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  {savedMsg}
                </>
              )}
            </span>
            <Button type="submit" disabled={saveMutation.isPending}>
              <Save className="h-4 w-4" />
              {saveMutation.isPending ? "Saving..." : "Save Preferences"}
            </Button>
          </div>
        </form>
      </Card>

      {/* Server-Side Provider Diagnostics */}
      {overview && (
        <Card className="p-6 space-y-4">
          <div>
            <h2 className="font-semibold text-base">Server-Side AI & Search Providers</h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              API keys are stored exclusively on the backend in <code>.env</code> and never exposed
              to the browser.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="rounded-lg border bg-background p-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold flex items-center gap-1.5">
                  <Cpu className="h-4 w-4 text-primary" />
                  LLM Provider
                </span>
                <Badge tone={overview.providers.llm_configured ? "success" : "danger"}>
                  {overview.providers.llm_configured ? "Configured" : "Missing Key"}
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground">
                Active: <code>{overview.providers.llm_provider}</code> (
                <code>{overview.providers.llm_model}</code>)
              </p>
              {overview.providers.llm_guidance && (
                <p className="text-xs text-amber-300/90">{overview.providers.llm_guidance}</p>
              )}
            </div>

            <div className="rounded-lg border bg-background p-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold flex items-center gap-1.5">
                  <Globe className="h-4 w-4 text-primary" />
                  Search Provider
                </span>
                <Badge tone={overview.providers.search_configured ? "success" : "danger"}>
                  {overview.providers.search_configured ? "Configured" : "Missing Key"}
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground">
                Active: <code>{overview.providers.search_provider}</code>
              </p>
              {overview.providers.search_guidance && (
                <p className="text-xs text-amber-300/90">{overview.providers.search_guidance}</p>
              )}
            </div>
          </div>
        </Card>
      )}

      {/* Usage Quota */}
      {overview && (
        <Card className="p-6 space-y-3">
          <h2 className="font-semibold text-base">Workspace Usage</h2>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div className="rounded-lg border bg-background p-3">
              <p className="text-xs text-muted-foreground">Projects</p>
              <p className="text-xl font-bold mt-1">{overview.usage.total_projects}</p>
            </div>
            <div className="rounded-lg border bg-background p-3">
              <p className="text-xs text-muted-foreground">Total Runs</p>
              <p className="text-xl font-bold mt-1">{overview.usage.total_runs}</p>
            </div>
            <div className="rounded-lg border bg-background p-3">
              <p className="text-xs text-muted-foreground">24h Quota</p>
              <p className="text-xl font-bold mt-1">
                {overview.usage.runs_last_24h} / {overview.usage.daily_limit}
              </p>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
