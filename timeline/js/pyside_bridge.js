(function (window) {
  "use strict";

  function safeApply(scope, fn) {
    var phase = scope.$root && scope.$root.$$phase;
    if (phase === "$apply" || phase === "$digest") {
      fn(scope);
    } else {
      scope.$apply(function () {
        fn(scope);
      });
    }
  }

  function withScope(callback, attempt) {
    attempt = attempt || 0;
    if (!window.angular || !document.body) {
      if (attempt > 40) {
        console.warn("timelineApi: Angular not ready");
        return;
      }
      return window.setTimeout(function () {
        withScope(callback, attempt + 1);
      }, 50);
    }

    var scope = window.angular.element(document.body).scope();
    if (!scope) {
      if (attempt > 40) {
        console.warn("timelineApi: scope not available");
        return;
      }
      return window.setTimeout(function () {
        withScope(callback, attempt + 1);
      }, 50);
    }

    callback(scope, function (fn) {
      safeApply(scope, fn);
    });
  }

  function getScope() {
    if (!window.angular || !document.body) {
      return null;
    }
    var scope = window.angular.element(document.body).scope();
    return scope || null;
  }

  function ensureProject(scope) {
    if (!scope.project) {
      scope.project = {};
    }
    if (!Array.isArray(scope.project.layers)) {
      scope.project.layers = [];
    }
    if (!Array.isArray(scope.project.clips)) {
      scope.project.clips = [];
    }
    if (!Array.isArray(scope.project.effects)) {
      scope.project.effects = [];
    }
    if (typeof scope.project.duration !== "number") {
      scope.project.duration = 0;
    }
    if (!scope.project.fps) {
      scope.project.fps = { num: 24, den: 1 };
    }
    return scope.project;
  }

  function toNumber(value, fallback) {
    var num = parseFloat(value);
    if (!isFinite(num)) {
      return typeof fallback === "number" ? fallback : 0;
    }
    return num;
  }

  function normalizeFps(input) {
    var defaultFps = { num: 24, den: 1 };
    if (typeof input === "number" && isFinite(input) && input > 0) {
      var scaled = Math.round(input * 1000);
      return { num: scaled, den: 1000 };
    }
    if (input && typeof input === "object") {
      var num = parseInt(input.num, 10);
      var den = parseInt(input.den, 10);
      if (!isFinite(num) || num <= 0) {
        return defaultFps;
      }
      if (!isFinite(den) || den <= 0) {
        den = 1;
      }
      return { num: num, den: den };
    }
    return defaultFps;
  }

  function normalizeClip(clip) {
    clip = clip || {};

    var defaults = {
      effects: [],
      images: { start: 0, end: 0 },
      alpha: { Points: [] },
      location_x: { Points: [] },
      location_y: { Points: [] },
      scale_x: { Points: [] },
      scale_y: { Points: [] },
      rotation: { Points: [] },
      time: { Points: [] },
      volume: { Points: [] },
      reader: { has_video: true, has_audio: true, fps: { num: 24, den: 1 } },
      file_id: "",
      show_audio: false,
      locked: false,
      position: 0,
      start: 0,
      duration: 1,
      end: 1,
      layer: 0,
      title: "",
      ui: {},
      color: "#5b8def",
      text_color: "#ffffff"
    };

    var normalized = Object.assign({}, defaults, clip);

    if (normalized.id == null) {
      normalized.id = "clip-" + Date.now();
    }

    normalized.position = toNumber(normalized.position, 0);
    normalized.start = toNumber(normalized.start, 0);
    normalized.layer = parseInt(normalized.layer, 10) || 0;

    var explicitDuration = clip && Object.prototype.hasOwnProperty.call(clip, "duration");
    var explicitEnd = clip && Object.prototype.hasOwnProperty.call(clip, "end");

    if (explicitDuration && !explicitEnd) {
      normalized.end = normalized.start + toNumber(normalized.duration, 0);
    } else if (!explicitDuration && explicitEnd) {
      normalized.end = toNumber(normalized.end, normalized.start);
      normalized.duration = Math.max(normalized.end - normalized.start, 0);
    } else {
      normalized.duration = toNumber(normalized.duration, 0);
      normalized.end = normalized.start + normalized.duration;
    }

    if (!normalized.reader) {
      normalized.reader = { has_video: true, has_audio: true, fps: { num: 24, den: 1 } };
    } else {
      if (typeof normalized.reader.has_video === "undefined") {
        normalized.reader.has_video = true;
      }
      if (typeof normalized.reader.has_audio === "undefined") {
        normalized.reader.has_audio = true;
      }
      if (!normalized.reader.fps) {
        normalized.reader.fps = { num: 24, den: 1 };
      } else {
        if (typeof normalized.reader.fps.num !== "number") {
          normalized.reader.fps.num = 24;
        }
        if (typeof normalized.reader.fps.den !== "number" || normalized.reader.fps.den === 0) {
          normalized.reader.fps.den = 1;
        }
      }
    }

    if (!normalized.ui) {
      normalized.ui = {};
    }

    return normalized;
  }

  function normalizeTrack(track) {
    track = track || {};

    var defaults = {
      id: "",
      number: 0,
      y: 0,
      label: "",
      lock: false,
      height: 60,
      color: "#d9d9d9"
    };

    var normalized = Object.assign({}, defaults, track);
    normalized.number = parseInt(normalized.number, 10);
    if (!isFinite(normalized.number)) {
      normalized.number = 0;
    }

    if (!normalized.id) {
      normalized.id = "L" + normalized.number;
    }

    return normalized;
  }

  function findTrack(scope, identifier) {
    var project = ensureProject(scope);
    var layers = project.layers;
    if (!layers.length) {
      return null;
    }

    var targetId = null;
    var targetNumber = null;

    if (identifier && typeof identifier === "object") {
      if (identifier.id) {
        targetId = identifier.id;
      }
      if (typeof identifier.number !== "undefined") {
        targetNumber = parseInt(identifier.number, 10);
      }
    } else if (typeof identifier === "string") {
      targetId = identifier;
      if (/^L-?\d+$/i.test(identifier)) {
        targetNumber = parseInt(identifier.slice(1), 10);
      }
    } else if (typeof identifier === "number") {
      targetNumber = identifier;
    }

    for (var i = 0; i < layers.length; i++) {
      var layer = layers[i];
      if (targetId !== null && layer.id === targetId) {
        return { layer: layer, index: i };
      }
      if (targetNumber !== null && layer.number === targetNumber) {
        return { layer: layer, index: i };
      }
    }
    return null;
  }

  function findClip(scope, clipId) {
    var project = ensureProject(scope);
    var clips = project.clips;
    for (var i = 0; i < clips.length; i++) {
      if (clips[i].id === clipId) {
        return { clip: clips[i], index: i };
      }
    }
    return null;
  }

  function updateClipTiming(clip) {
    clip.start = toNumber(clip.start, 0);
    clip.duration = toNumber(clip.duration, clip.end - clip.start);
    if (clip.duration < 0) {
      clip.duration = 0;
    }
    clip.end = toNumber(clip.end, clip.start + clip.duration);
    if (!Object.prototype.hasOwnProperty.call(clip, "end")) {
      clip.end = clip.start + clip.duration;
    }
    if (!Object.prototype.hasOwnProperty.call(clip, "duration")) {
      clip.duration = Math.max(clip.end - clip.start, 0);
    }
  }

  function updateProjectDuration(scope, clip) {
    var clipDuration = clip.duration || 0;
    var basePosition = typeof clip.position === "number" ? clip.position : (clip.start || 0);
    var clipEnd = basePosition + clipDuration;
    var project = ensureProject(scope);
    project.duration = Math.max(project.duration || 0, clipEnd);
  }

  function recomputeProjectDuration(scope, options) {
    options = options || {};
    var allowShrink = options.allowShrink === true;
    var project = ensureProject(scope);
    var clips = project.clips || [];
    var maxEnd = 0;
    for (var i = 0; i < clips.length; i++) {
      var c = clips[i];
      var position = typeof c.position === "number" ? c.position : toNumber(c.start, 0);
      var duration = toNumber(c.duration, c.end - c.start);
      if (duration < 0) {
        duration = 0;
      }
      var end = position + duration;
      if (end > maxEnd) {
        maxEnd = end;
      }
    }
    if (allowShrink) {
      project.duration = maxEnd;
    } else {
      project.duration = Math.max(project.duration || 0, maxEnd);
    }
  }

  function scheduleLayerIndexUpdate(scope) {
    if (typeof scope.updateLayerIndex !== "function") {
      return;
    }
    var invoke = function () {
      if (typeof scope.$applyAsync === "function") {
        scope.$applyAsync(function () {
          scope.updateLayerIndex();
        });
      } else if (typeof scope.$evalAsync === "function") {
        scope.$evalAsync(function () {
          scope.updateLayerIndex();
        });
      } else {
        scope.updateLayerIndex();
      }
    };
    [0, 50, 150].forEach(function (delay) {
      window.setTimeout(invoke, delay);
    });
  }

  function refreshTimeline(scope, options) {
    options = options || {};
    var allowShrink = options.allowShrink === true;
    if (typeof scope.sortItems === "function" && options.sort !== false) {
      scope.sortItems();
    }
    if (typeof scope.resizeTimeline === "function" && options.resize !== false) {
      scope.resizeTimeline();
    }
    if (options.recomputeDuration !== false) {
      recomputeProjectDuration(scope, { allowShrink: allowShrink });
    }
    if (options.updateLayers !== false) {
      scheduleLayerIndexUpdate(scope);
    }
  }

  function removeClipsFromTrack(scope, trackNumber) {
    var project = ensureProject(scope);
    project.clips = (project.clips || []).filter(function (clip) {
      return clip.layer !== trackNumber;
    });
  }

  var api = window.timelineApi || {};

  api.addClip = function (clip) {
    withScope(function (scope, apply) {
      var normalized = normalizeClip(clip);
      apply(function () {
        var project = ensureProject(scope);
        var clips = project.clips;
        var existing = findClip(scope, normalized.id);

        if (existing) {
          Object.assign(existing.clip, normalized);
          updateClipTiming(existing.clip);
        } else {
          clips.push(normalized);
        }

        updateProjectDuration(scope, normalized);
        refreshTimeline(scope);
      });
    });
  };

  api.updateClip = function (clipId, patch) {
    withScope(function (scope, apply) {
      apply(function () {
        var target = findClip(scope, clipId);
        if (!target) {
          return;
        }
        var clip = target.clip;
        Object.assign(clip, patch || {});
        if (typeof clip.layer !== "undefined") {
          clip.layer = parseInt(clip.layer, 10) || 0;
        }
        if (typeof clip.position !== "undefined") {
          clip.position = toNumber(clip.position, clip.position);
        }
        if (patch && Object.prototype.hasOwnProperty.call(patch, "start")) {
          clip.start = toNumber(patch.start, clip.start);
        }
        if (patch && Object.prototype.hasOwnProperty.call(patch, "duration")) {
          clip.duration = toNumber(patch.duration, clip.duration);
        }
        if (patch && Object.prototype.hasOwnProperty.call(patch, "end")) {
          clip.end = toNumber(patch.end, clip.end);
        }
        if (patch && Object.prototype.hasOwnProperty.call(patch, "color") && !patch.color) {
          delete clip.color;
        }
        if (patch && Object.prototype.hasOwnProperty.call(patch, "text_color") && !patch.text_color) {
          delete clip.text_color;
        }
        updateClipTiming(clip);
        refreshTimeline(scope);
      });
    });
  };

  api.moveClip = function (clipId, targetLayer, position, options) {
    options = options || {};
    withScope(function (scope, apply) {
      apply(function () {
        var target = findClip(scope, clipId);
        if (!target) {
          return;
        }
        var clip = target.clip;

        if (typeof targetLayer !== "undefined" && targetLayer !== null) {
          var trackInfo = findTrack(scope, targetLayer);
          if (trackInfo) {
            clip.layer = trackInfo.layer.number;
          }
        }

        if (typeof position !== "undefined" && position !== null) {
          clip.position = toNumber(position, clip.position);
        }

        if (options.start !== undefined) {
          clip.start = toNumber(options.start, clip.start);
        }
        if (options.duration !== undefined) {
          clip.duration = toNumber(options.duration, clip.duration);
        }
        if (options.end !== undefined) {
          clip.end = toNumber(options.end, clip.end);
        }

        updateClipTiming(clip);
        refreshTimeline(scope);
      });
    });
  };

  api.removeClip = function (clipId) {
    withScope(function (scope, apply) {
      apply(function () {
        var project = ensureProject(scope);
        var clips = project.clips;
        var removed = false;
        for (var i = clips.length - 1; i >= 0; i--) {
          if (clips[i].id === clipId) {
            clips.splice(i, 1);
            removed = true;
            break;
          }
        }

        if (removed) {
          refreshTimeline(scope);
        }
      });
    });
  };

  api.setClipColor = function (clipId, color, textColor) {
    api.updateClip(clipId, {
      color: color,
      text_color: textColor
    });
  };

  api.addTrack = function (track) {
    withScope(function (scope, apply) {
      var normalized = normalizeTrack(track);
      apply(function () {
        var project = ensureProject(scope);
        var layers = project.layers;
        var existingInfo = findTrack(scope, normalized);

        if (existingInfo) {
          Object.assign(existingInfo.layer, normalized);
        } else {
          layers.push(normalized);
          layers.sort(function (a, b) {
            return (a.number || 0) - (b.number || 0);
          });
        }

        refreshTimeline(scope, { recomputeDuration: false });
      });
    });
  };

  api.removeTrack = function (identifier, options) {
    options = options || {};
    withScope(function (scope, apply) {
      apply(function () {
        var project = ensureProject(scope);
        var result = findTrack(scope, identifier);
        if (!result) {
          return;
        }

        var trackNumber = result.layer.number;
        project.layers.splice(result.index, 1);

        if (!options.keepClips) {
          removeClipsFromTrack(scope, trackNumber);
        }

        refreshTimeline(scope, { allowShrink: options.allowShrink === true });
      });
    });
  };

  api.resizeTimeline = function (duration, options) {
    options = options || {};
    withScope(function (scope, apply) {
      apply(function () {
        var project = ensureProject(scope);
        var currentDuration = project.duration || 0;
        var target = toNumber(duration, currentDuration);
        if (target < 0) {
          target = 0;
        }
        var allowShrink = options.allowShrink !== false;

        var clips = project.clips || [];
        var maxEnd = 0;
        for (var i = 0; i < clips.length; i++) {
          var clip = clips[i];
          var clipPos = typeof clip.position === "number" ? clip.position : toNumber(clip.start, 0);
          var clipDur = toNumber(clip.duration, clip.end - clip.start);
          if (clipDur < 0) {
            clipDur = 0;
          }
          var clipEnd = clipPos + clipDur;
          if (clipEnd > maxEnd) {
            maxEnd = clipEnd;
          }
        }

        if (!allowShrink && target < currentDuration) {
          target = currentDuration;
        }

        if (target < maxEnd) {
          target = maxEnd;
        }

        project.duration = target;
        refreshTimeline(scope, { recomputeDuration: false });
      });
    });
  };

  api.setProjectState = function (projectState) {
    withScope(function (scope, apply) {
      apply(function () {
        scope.loadJson({ value: projectState });
      });
    });
  };

  api.collectTimelineInfo = function () {
    var scope = getScope();
    if (!scope) {
      return null;
    }

    var project = ensureProject(scope);
    var snapshot = window.angular.copy(project);
    var layers = snapshot.layers || [];
    var clips = snapshot.clips || [];

    var tracks = layers.map(function (layer) {
      var layerNumber = typeof layer.number === "number" ? layer.number : parseInt(layer.number, 10) || 0;
      var trackClips = [];
      for (var i = 0; i < clips.length; i++) {
        var clip = clips[i];
        var clipLayer = typeof clip.layer === "number" ? clip.layer : parseInt(clip.layer, 10) || 0;
        if (clipLayer === layerNumber) {
          trackClips.push(window.angular.copy(clip));
        }
      }
      var trackCopy = window.angular.copy(layer);
      trackCopy.clips = trackClips;
      return trackCopy;
    });

    return {
      fps: snapshot.fps || { num: 24, den: 1 },
      duration: typeof snapshot.duration === "number" ? snapshot.duration : 0,
      tracks: tracks,
      clips: window.angular.copy(clips)
    };
  };

  api.emitProjectState = function () {
    withScope(function (scope) {
      var snapshot = window.angular.copy(ensureProject(scope));
      if (window.timeline && typeof timeline.invoke === "function") {
        timeline.invoke("project_state", [JSON.stringify(snapshot)]);
      } else if (window.timeline && typeof timeline.qt_log === "function") {
        timeline.qt_log("WARN", "timelineApi.emitProjectState: timeline backend missing invoke()");
      } else {
        console.warn("timelineApi.emitProjectState: timeline backend not ready");
      }
    });
  };

  api.movePlayhead = function (seconds) {
    withScope(function (scope, apply) {
      var value = parseFloat(seconds) || 0;
      apply(function () {
        scope.movePlayhead(value);
        scope.previewFrame(value);
      });
    });
  };

  api.setPlayheadPlaying = function (playing, options) {
    withScope(function (scope, apply) {
      apply(function () {
        var opts = options || {};
        if (playing) {
          if (typeof scope.playPlayhead === "function") {
            scope.playPlayhead(opts);
          }
        } else if (typeof scope.pausePlayhead === "function") {
          scope.pausePlayhead();
        }
      });
    });
  };

  api.togglePlayhead = function (options) {
    withScope(function (scope, apply) {
      apply(function () {
        if (typeof scope.togglePlayhead === "function") {
          scope.togglePlayhead(options || {});
        }
      });
    });
  };

  api.setFrameRate = function (input) {
    withScope(function (scope, apply) {
      apply(function () {
        var project = ensureProject(scope);
        project.fps = normalizeFps(input);
        refreshTimeline(scope, { recomputeDuration: false });
      });
    });
  };

  window.timelineApi = api;
})(window);
