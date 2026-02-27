/**
 * Diagnostic Storefront - AI Supplement Protocol Generator
 * Design: Mission Control with warm wellness accents
 * Consultative UI where users enter health goals and receive AI-generated protocols.
 */
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Stethoscope,
  Sparkles,
  Loader2,
  Pill,
  Clock,
  BookOpen,
  Plus,
  X,
  FlaskConical,
  HeartPulse,
} from "lucide-react";
import { generateProtocol } from "@/lib/api";
import { toast } from "sonner";

const WELLNESS_IMG = "https://private-us-east-1.manuscdn.com/sessionFile/wrtUf2bzqlcbMnFN5Kbroe/sandbox/M6g0BKFQi4swuwmDLfZbzd-img-2_1771848946000_na1fn_ZGlhZ25vc3RpYy13ZWxsbmVzcw.png?x-oss-process=image/resize,w_1920,h_1920/format,webp/quality,q_80&Expires=1798761600&Policy=eyJTdGF0ZW1lbnQiOlt7IlJlc291cmNlIjoiaHR0cHM6Ly9wcml2YXRlLXVzLWVhc3QtMS5tYW51c2Nkbi5jb20vc2Vzc2lvbkZpbGUvd3J0VWYyYnpxbGNiTW5GTjVLYnJvZS9zYW5kYm94L002ZzBCS0ZRaTRzd3V3bURMZlpiemQtaW1nLTJfMTc3MTg0ODk0NjAwMF9uYTFmbl9aR2xoWjI1dmMzUnBZeTEzWld4c2JtVnpjdy5wbmc~eC1vc3MtcHJvY2Vzcz1pbWFnZS9yZXNpemUsd18xOTIwLGhfMTkyMC9mb3JtYXQsd2VicC9xdWFsaXR5LHFfODAiLCJDb25kaXRpb24iOnsiRGF0ZUxlc3NUaGFuIjp7IkFXUzpFcG9jaFRpbWUiOjE3OTg3NjE2MDB9fX1dfQ__&Key-Pair-Id=K2HSFNDJXOU9YS&Signature=r3pjX5dWi60IzzeCGLKHdRyjbu2Oe1JPEHjERu0ubRgLwvrSRIuwjme1Yf5-dibngghpRV-wRM69Qlh6mGxr28izoiysziRj8ti6LYha8CaJ4-oFKW4LjvQJYw6OuRkli4OwGwsQbxd3e6oaoro937A1EQ9xRjSYuIf4TKJ3RgE9mpgs~hfaiAtFT9WV~CbDHiykSw5a5je-ECjQHwlCqAL~NFFQDH~W4RLRcbMTHsUumbmuNrc~9IvU5j-gHYlAHRQxrN7zNZjj8XviazxsbP6c1pxkPX6dhoKd~onKRoWwNQzQCs1XXxfWGt48yKJmT4sVOrSvr-xwKY3dU~YcwQ__";

const HEALTH_GOALS = [
  "Better Sleep",
  "Stress Relief",
  "Joint Health",
  "Gut Health",
  "Immune Support",
  "Energy & Focus",
  "Heart Health",
  "Skin & Hair",
  "Muscle Recovery",
  "Anti-Inflammation",
];

export default function DiagnosticStorefront() {
  const [selectedGoals, setSelectedGoals] = useState<string[]>([]);
  const [age, setAge] = useState("");
  const [gender, setGender] = useState("");
  const [protocol, setProtocol] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const toggleGoal = (goal: string) => {
    setSelectedGoals((prev) =>
      prev.includes(goal) ? prev.filter((g) => g !== goal) : [...prev, goal]
    );
  };

  const handleGenerate = async () => {
    if (selectedGoals.length === 0) {
      toast.error("Please select at least one health goal");
      return;
    }
    setLoading(true);
    try {
      const result = await generateProtocol({
        goals: selectedGoals,
        age: age ? parseInt(age) : undefined,
        gender: gender || undefined,
      });
      setProtocol(result);
      toast.success("Protocol generated successfully");
    } catch (e: any) {
      toast.error(`Failed: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 animate-fade-in-up">
      {/* Hero */}
      <div className="relative rounded-xl overflow-hidden h-52">
        <img
          src={WELLNESS_IMG}
          alt="Wellness Consultation"
          className="absolute inset-0 w-full h-full object-cover opacity-30"
        />
        <div className="absolute inset-0 bg-gradient-to-r from-background via-background/85 to-transparent" />
        <div className="relative z-10 flex items-center h-full px-8">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <HeartPulse className="w-5 h-5 text-primary" />
              <span className="text-xs font-mono text-primary uppercase tracking-widest">
                staging.kayapure.pk
              </span>
            </div>
            <h1 className="text-2xl font-bold text-foreground">
              Diagnostic Storefront
            </h1>
            <p className="text-sm text-muted-foreground mt-1 max-w-lg">
              Science-backed supplement protocols tailored to your health goals.
              Powered by AI analysis of clinical research and nutritional science.
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Input Form */}
        <div className="space-y-4">
          <Card className="panel-border">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <Stethoscope className="w-4 h-4 text-primary" />
                Your Health Goals
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap gap-2">
                {HEALTH_GOALS.map((goal) => (
                  <button
                    key={goal}
                    onClick={() => toggleGoal(goal)}
                    className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-all duration-200 ${
                      selectedGoals.includes(goal)
                        ? "bg-primary/15 text-primary border-primary/40 glow-cyan-sm"
                        : "bg-accent/50 text-muted-foreground border-border hover:text-foreground hover:border-primary/30"
                    }`}
                  >
                    {selectedGoals.includes(goal) && <span className="mr-1">&#10003;</span>}
                    {goal}
                  </button>
                ))}
              </div>

              <div className="grid grid-cols-2 gap-3 pt-2">
                <div>
                  <Label className="text-xs text-muted-foreground">Age</Label>
                  <Input
                    type="number"
                    placeholder="e.g., 35"
                    value={age}
                    onChange={(e) => setAge(e.target.value)}
                    className="mt-1 bg-input border-border text-sm"
                  />
                </div>
                <div>
                  <Label className="text-xs text-muted-foreground">Gender</Label>
                  <Input
                    type="text"
                    placeholder="e.g., Male"
                    value={gender}
                    onChange={(e) => setGender(e.target.value)}
                    className="mt-1 bg-input border-border text-sm"
                  />
                </div>
              </div>

              <Button
                onClick={handleGenerate}
                disabled={loading || selectedGoals.length === 0}
                className="w-full glow-cyan"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Analyzing Research...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4 mr-2" />
                    Generate Protocol
                  </>
                )}
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Protocol Results */}
        <div className="space-y-4">
          {protocol ? (
            <>
              <Card className="panel-border glow-cyan-sm">
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm font-semibold flex items-center gap-2">
                    <FlaskConical className="w-4 h-4 text-primary" />
                    {protocol.protocol_name}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {protocol.recommendations?.map((rec: any, i: number) => (
                    <div
                      key={i}
                      className="p-3 rounded-lg bg-accent/30 border border-border animate-slide-in"
                      style={{ animationDelay: `${i * 100}ms` }}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex items-center gap-2">
                          <Pill className="w-4 h-4 text-primary shrink-0" />
                          <h4 className="text-sm font-semibold text-foreground">
                            {rec.product_name}
                          </h4>
                        </div>
                        <Badge variant="outline" className="text-[10px] font-mono text-primary">
                          {(rec.confidence_score * 100).toFixed(0)}% confidence
                        </Badge>
                      </div>
                      <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
                        <div className="flex items-center gap-1.5 text-muted-foreground">
                          <span className="font-semibold text-foreground/80">Dosage:</span>
                          {rec.dosage}
                        </div>
                        <div className="flex items-center gap-1.5 text-muted-foreground">
                          <Clock className="w-3 h-3 shrink-0" />
                          {rec.timing}
                        </div>
                      </div>
                      <p className="text-xs text-muted-foreground mt-2 leading-relaxed">
                        {rec.scientific_basis}
                      </p>
                    </div>
                  ))}
                </CardContent>
              </Card>

              {/* Disclaimer & Sources */}
              <Card className="panel-border">
                <CardContent className="py-4">
                  <p className="text-[11px] text-muted-foreground leading-relaxed">
                    <span className="font-semibold text-amber-warn">Disclaimer:</span>{" "}
                    {protocol.disclaimer}
                  </p>
                  {protocol.sources?.length > 0 && (
                    <div className="mt-3">
                      <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1 flex items-center gap-1">
                        <BookOpen className="w-3 h-3" />
                        Scientific References
                      </p>
                      <ul className="space-y-0.5">
                        {protocol.sources.map((src: string, i: number) => (
                          <li key={i} className="text-[10px] text-muted-foreground/70 font-mono">
                            [{i + 1}] {src}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </CardContent>
              </Card>
            </>
          ) : (
            <Card className="panel-border">
              <CardContent className="py-16 text-center">
                <Sparkles className="w-10 h-10 text-muted-foreground/20 mx-auto mb-3" />
                <p className="text-sm text-muted-foreground">
                  Select your health goals and generate a personalized protocol
                </p>
                <p className="text-xs text-muted-foreground/60 mt-1">
                  Our AI analyzes clinical research to create science-backed recommendations
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
