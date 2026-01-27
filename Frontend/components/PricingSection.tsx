import { Check, Zap, Smartphone, Info } from "lucide-react";

export default function PricingSection() {
  return (
    <section className="py-20 px-4 bg-white" id="pricing">
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-5xl font-bold text-slate-900 mb-4">
            Pricing Plans
          </h2>
          <p className="text-lg text-slate-600 max-w-2xl mx-auto">
            Subscribe via our website to get <span className="text-green-600 font-bold">Exclusive Discounts</span> and avoid App Store surcharges.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-16">

          {/* Basic Plan */}
          <div className="border border-slate-200 rounded-2xl p-8 hover:border-slate-300 transition-colors flex flex-col">
            <h3 className="text-xl font-bold text-slate-900 mb-2">Telegram Bot</h3>
            <div className="text-4xl font-extrabold text-slate-900 mb-1">₹69<span className="text-lg font-normal text-slate-500">/mo</span></div>
            <p className="text-sm text-slate-500 mb-6">For casual savers.</p>
            <ul className="space-y-3 text-sm text-slate-600 mb-8 flex-grow">
              <li className="flex gap-2"><Check size={18} className="text-slate-400" /> Telegram Bot Access</li>
              <li className="flex gap-2"><Check size={18} className="text-slate-400" /> 10 Searches / Day</li>
            </ul>
            <button className="w-full py-3 px-6 rounded-xl border border-slate-900 text-slate-900 font-bold hover:bg-slate-50 transition-colors">
              Subscribe Basic
            </button>
          </div>

          {/* PRO Plan - HERO */}
          <div className="border-2 border-green-500 rounded-2xl p-8 bg-green-50/20 relative transform md:-translate-y-4 shadow-xl flex flex-col">
            <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-green-600 text-white px-4 py-1 rounded-full text-xs font-bold tracking-wider shadow-sm">
              BEST SELLER
            </div>
            <div className="flex justify-between items-start">
              <h3 className="text-xl font-bold text-slate-900 mb-2">Smart Saver PRO</h3>
              <Smartphone size={20} className="text-green-600"/>
            </div>
            <div className="text-4xl font-extrabold text-green-600 mb-1">₹59<span className="text-lg font-normal text-slate-500">/mo</span></div>
            <div className="flex items-center gap-2 mb-6">
               <span className="text-sm line-through text-slate-400">₹89 Standard</span>
               <span className="bg-green-100 text-green-700 text-xs font-bold px-2 py-0.5 rounded">WEB EXCLUSIVE</span>
            </div>
            <ul className="space-y-3 text-sm text-slate-700 mb-8 flex-grow">
              <li className="flex gap-2"><Zap size={18} className="text-green-600" /> <strong>Unlimited App Access</strong></li>
              <li className="flex gap-2"><Check size={18} className="text-green-600" /> WhatsApp + Telegram Bots</li>
              <li className="flex gap-2"><Check size={18} className="text-green-600" /> Auto-Apply Coupon Finder</li>
            </ul>
            <button className="w-full py-3 px-6 rounded-xl bg-green-600 text-white font-bold hover:bg-green-700 transition-colors shadow-lg shadow-green-200 mb-2">
              Subscribe Now (Save 33%)
            </button>
            <p className="text-xs text-center text-slate-500">*Purchase here, then login to App.</p>
          </div>

          {/* Yearly Plan */}
          <div className="border border-slate-200 rounded-2xl p-8 hover:border-purple-200 transition-colors flex flex-col">
            <h3 className="text-xl font-bold text-slate-900 mb-2">Yearly Pass</h3>
            <div className="text-4xl font-extrabold text-slate-900 mb-1">₹49<span className="text-lg font-normal text-slate-500">/mo</span></div>
            <p className="text-sm text-slate-500 mb-6">Billed ₹588 yearly.</p>
            <ul className="space-y-3 text-sm text-slate-600 mb-8 flex-grow">
              <li className="flex gap-2"><Check size={18} className="text-purple-500" /> <strong>Lowest Possible Rate</strong></li>
              <li className="flex gap-2"><Check size={18} className="text-purple-500" /> Lock in price for 1 year</li>
              <li className="flex gap-2"><Check size={18} className="text-purple-500" /> Priority Support</li>
            </ul>
            <button className="w-full py-3 px-6 rounded-xl bg-slate-900 text-white font-bold hover:bg-slate-800 transition-colors">
              Get Yearly Access
            </button>
          </div>
        </div>

        {/* Mass Adoption - Student/Family */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-12 border-t border-slate-100">
           <div className="p-4 bg-slate-50 rounded-xl">
              <h4 className="font-bold text-slate-900">Student Plan</h4>
              <p className="text-sm text-slate-500">₹39/mo with ID card.</p>
           </div>
           <div className="p-4 bg-slate-50 rounded-xl">
              <h4 className="font-bold text-slate-900">Couple Plan</h4>
              <p className="text-sm text-slate-500">₹119/mo (2 accounts).</p>
           </div>
           <div className="p-4 bg-slate-50 rounded-xl">
              <h4 className="font-bold text-slate-900">Family Plan</h4>
              <p className="text-sm text-slate-500">₹199/mo (4 accounts).</p>
           </div>
        </div>
      </div>
    </section>
  );
}