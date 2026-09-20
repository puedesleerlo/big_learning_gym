import { useCallback, useEffect, useRef, useState } from "react";

export function useResource(load, dependencies = []) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const generation = useRef(0);
  const loader = useRef(load);
  loader.current = load;
  const reload = useCallback(async () => {
    const ticket = ++generation.current;
    setLoading(true);
    try {
      const value = await loader.current();
      if (ticket === generation.current) {
        setData(value);
        setError(null);
      }
      return value;
    } catch (e) {
      if (ticket === generation.current) setError(e);
      return null;
    } finally {
      if (ticket === generation.current) setLoading(false);
    }
  }, []);
  useEffect(() => {
    setData(null);
    reload();
    return () => {
      generation.current++;
    };
  }, dependencies);
  return { data, error, loading, reload, setData };
}

function useClock(id, record, perform) {
  const current = useRef({ record, perform });
  current.current = { record, perform };
  const [clockError, setClockError] = useState(null);
  useEffect(() => {
    if (!id) return;
    let autoResume = false;
    const send = (action) =>
      current.current
        .perform(action, id)
        .then(() => setClockError(null))
        .catch(setClockError);
    const interval = setInterval(() => {
      if (current.current.record?.running && !document.hidden)
        send("heartbeat");
    }, 15000);
    const visibility = () => {
      if (document.hidden && current.current.record?.running) {
        autoResume = true;
        send("pause");
      } else if (
        !document.hidden &&
        autoResume &&
        current.current.record?.status === "active"
      ) {
        autoResume = false;
        send("resume");
      }
    };
    document.addEventListener("visibilitychange", visibility);
    const leave = () => {
      if (current.current.record?.running) send("pause");
    };
    window.addEventListener("pagehide", leave);
    return () => {
      clearInterval(interval);
      document.removeEventListener("visibilitychange", visibility);
      window.removeEventListener("pagehide", leave);
      if (
        current.current.record?.id === id &&
        current.current.record?.running &&
        current.current.record?.status === "active"
      )
        current.current.perform("pause", id).catch(() => {});
    };
  }, [id]);
  return clockError;
}

export function useLabVisit(client, labId, lessonId) {
  const resource = useResource(async () => {
    const lab = await client.lab(labId);
    const visits = lab.activities.filter((v) => v.lesson_id === lessonId);
    const saved =
      [...visits].reverse().find((v) => v.status === "active") || visits.at(-1);
    return saved ? client.visit(saved.id) : null;
  }, [client, labId, lessonId]);
  const current = useRef(resource.data);
  current.current = resource.data;
  const set = (value) => {
    current.current = value;
    resource.setData(value);
    return value;
  };
  const event = async (action, extra) => {
    if (!current.current) throw new Error("Start the lesson first.");
    return set(await client.event(current.current.id, action, extra));
  };
  const clockError = useClock(
    resource.data?.id,
    resource.data,
    async (action, id) => {
      const updated = await client.event(id, action);
      if (current.current?.id === id) set(updated);
    },
  );
  return {
    ...resource,
    clockError,
    event,
    async start(lesson) {
      if (current.current?.status === "active") return event("resume");
      const visit = await client.startVisit(labId, lesson);
      set(visit);
      return event("reading", { parameters: { section: "lesson" } });
    },
    async discuss(request) {
      try {
        return await client.discuss(current.current.id, request);
      } finally {
        set(await client.visit(current.current.id));
      }
    },
    async practice(spec) {
      if (current.current?.status === "active") {
        await event("reading", {
          parameters: { section: "lesson_before_practice" },
        });
        await event("pause");
      }
      const session = await client.startLinkedPractice(current.current, spec);
      set(await client.visit(current.current.id));
      return session;
    },
  };
}

export function usePracticeSession(client, id) {
  const resource = useResource(() => client.session(id), [client, id]);
  const current = useRef(resource.data);
  current.current = resource.data;
  const timer = async (action, itemId) => {
    const update = await client.timer(id, action, itemId);
    if (current.current) {
      current.current = { ...current.current, ...update };
      resource.setData(current.current);
    }
    return update;
  };
  const clockError = useClock(id, resource.data, (action) => timer(action));
  return {
    ...resource,
    clockError,
    timer,
    async answer(itemId, value, confidence) {
      const result = await client.answer(id, itemId, value, confidence);
      current.current = result;
      resource.setData(result);
      return result;
    },
    async finish(blocker) {
      const result = await client.finish(id, blocker);
      current.current = result;
      resource.setData(result);
      return result;
    },
  };
}
