import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import aboutHe from "./locales/he/about.json";
import adminHe from "./locales/he/admin.json";
import authHe from "./locales/he/auth.json";
import candidateHe from "./locales/he/candidate.json";
import commonHe from "./locales/he/common.json";
import companyHe from "./locales/he/company.json";
import cookiesHe from "./locales/he/cookies.json";
import dashboardHe from "./locales/he/dashboard.json";
import landingHe from "./locales/he/landing.json";
import legalHe from "./locales/he/legal.json";
import navHe from "./locales/he/nav.json";
import publicJobsHe from "./locales/he/publicJobs.json";
import resumeHe from "./locales/he/resume.json";
import uiHe from "./locales/he/ui.json";

i18n.use(initReactI18next).init({
  resources: {
    he: {
      about: aboutHe,
      admin: adminHe,
      auth: authHe,
      candidate: candidateHe,
      common: commonHe,
      company: companyHe,
      cookies: cookiesHe,
      dashboard: dashboardHe,
      landing: landingHe,
      legal: legalHe,
      nav: navHe,
      publicJobs: publicJobsHe,
      resume: resumeHe,
      ui: uiHe,
    },
  },
  lng: "he",
  defaultNS: "common",
  ns: [
    "about",
    "admin",
    "auth",
    "candidate",
    "common",
    "company",
    "cookies",
    "dashboard",
    "landing",
    "legal",
    "nav",
    "publicJobs",
    "resume",
    "ui",
  ],
  interpolation: { escapeValue: false },
});

export default i18n;
