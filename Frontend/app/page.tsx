import BotHero from "@/components/BotHero";
import PricingSection from "@/components/PricingSection";

export default function Home() {
  return (
    <main className="min-h-screen bg-white">
      {/* Navigation */}
      <nav className="flex items-center justify-between px-6 py-4 bg-white/80 backdrop-blur-md sticky top-0 z-50 border-b border-slate-100">
        <div className="text-2xl font-bold text-green-600 tracking-tighter">Smart Saver AI</div>
        <div className="flex gap-4">
          <button className="text-sm font-medium text-slate-600 hover:text-green-600">Login</button>
          <button className="text-sm font-bold bg-slate-900 text-white px-4 py-2 rounded-lg hover:bg-slate-800">
            Get App
          </button>
        </div>
      </nav>

      <BotHero />
      <PricingSection />

      <footer className="bg-slate-50 py-12 text-center text-slate-500 text-sm">
        <p>© 2026 Smart Saver AI. All rights reserved.</p>
        <p className="mt-2">Made with ❤️ in Bengaluru.</p>
      </footer>
    </main>
  );
}