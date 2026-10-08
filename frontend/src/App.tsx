import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { PageSkeleton } from "./components/ui";
import { RequireAuth } from "./lib/auth";
import Challenges from "./pages/Challenges";
import Dashboard from "./pages/Dashboard";
import Advisor from "./pages/Advisor";
import Exchange from "./pages/Exchange";
import Landing from "./pages/Landing";
import Leaderboard from "./pages/Leaderboard";
import Login from "./pages/Login";
import Pickup from "./pages/Pickup";
import Recyclers from "./pages/Recyclers";
import Scan from "./pages/Scan";

const Impact = lazy(() => import("./pages/Impact"));
const Organization = lazy(() => import("./pages/Organization"));
const Ops = lazy(() => import("./pages/Ops"));
const lazyPage = (el: JSX.Element) => <Suspense fallback={<PageSkeleton />}>{el}</Suspense>;

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route element={<RequireAuth><Layout /></RequireAuth>}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/scan" element={<Scan />} />
        <Route path="/exchange" element={<Exchange />} />
        <Route path="/recyclers" element={<Recyclers />} />
        <Route path="/pickup" element={<Pickup />} />
        <Route path="/leaderboard" element={<Leaderboard />} />
        <Route path="/challenges" element={<Challenges />} />
        <Route path="/impact" element={lazyPage(<Impact />)} />
        <Route path="/advisor" element={<Advisor />} />
        <Route path="/org" element={lazyPage(<Organization />)} />
        <Route path="/ops" element={<RequireAuth roles={["ADMIN", "COLLECTOR"]}>{lazyPage(<Ops />)}</RequireAuth>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
