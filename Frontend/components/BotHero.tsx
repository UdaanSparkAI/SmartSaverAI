import { Send, MessageCircle } from "lucide-react";

export default function BotHero() {
  return (
    <section className="flex flex-col items-center justify-center py-20 px-4 bg-gradient-to-br from-green-50 to-blue-50">
      <div className="bg-green-100 text-green-800 text-xs font-bold px-3 py-1 rounded-full mb-6 uppercase tracking-wide">
        v1.0 Live for Blinkit & Zepto
      </div>

      <h1 className="text-4xl md:text-6xl font-extrabold text-center text-slate-900 mb-6 leading-tight">
        Stop Overpaying on <br/>
        <span className="text-green-600">Quick Commerce</span>
      </h1>

      <p className="text-lg text-slate-600 mb-8 text-center max-w-2xl">
        Our AI scrapes real-time prices across Blinkit, Zepto, and Swiggy Instamart to find you the absolute lowest price instantly.
      </p>

      <div className="flex flex-col sm:flex-row gap-4 w-full max-w-md">
        <button className="flex-1 flex items-center justify-center gap-2 bg-blue-500 hover:bg-blue-600 text-white py-3 px-6 rounded-xl font-bold transition-all shadow-lg shadow-blue-200">
          <Send size={20} />
          Join Telegram Bot
        </button>
        <button className="flex-1 flex items-center justify-center gap-2 bg-green-500 hover:bg-green-600 text-white py-3 px-6 rounded-xl font-bold transition-all shadow-lg shadow-green-200">
          <MessageCircle size={20} />
          Chat on WhatsApp
        </button>
      </div>

      <div className="mt-8 flex items-center gap-2 text-sm text-slate-500">
        <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
        1,204 users saving money right now
      </div>
    </section>
  );
}