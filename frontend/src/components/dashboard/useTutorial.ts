import { useEffect, useRef, useCallback } from 'react';
import { driver, DriveStep, Config } from 'driver.js';
import 'driver.js/dist/driver.css';
import '@/styles/tutorial.css';

const TUTORIAL_STORAGE_KEY = 'aria-tutorial-completed';
const TUTORIAL_VERSION = 'v19'; // Increment this to force tutorial reset

// Log version on load for debugging
console.log('[TUTORIAL] Loading version:', TUTORIAL_VERSION, 'at', new Date().toISOString());

// Tutorial flags for interactive demo
export const TUTORIAL_DEMO_READY = 'aria-tutorial-demo-ready';
export const TUTORIAL_DEMO_SCENARIO = 'aria-tutorial-demo-scenario';

export const useTutorial = () => {
  const driverRef = useRef<ReturnType<typeof driver> | null>(null);

  // Clean up old tutorial data on mount and ensure version is set
  useEffect(() => {
    const completedVersion = localStorage.getItem('aria-tutorial-version');
    const hasCompletedTutorial = localStorage.getItem(TUTORIAL_STORAGE_KEY);
    
    // If no version is set at all, set it now (first visit)
    if (!completedVersion) {
      console.log('[TUTORIAL] First visit detected - setting version:', TUTORIAL_VERSION);
      localStorage.setItem('aria-tutorial-version', TUTORIAL_VERSION);
    }
    
    if (completedVersion && completedVersion !== TUTORIAL_VERSION) {
      // Clear all old tutorial data if version changed
      console.log('[TUTORIAL] Version mismatch - clearing old data. Old:', completedVersion, 'New:', TUTORIAL_VERSION);
      localStorage.removeItem(TUTORIAL_STORAGE_KEY);
      localStorage.removeItem(TUTORIAL_DEMO_READY);
      localStorage.removeItem(TUTORIAL_DEMO_SCENARIO);
      localStorage.setItem('aria-tutorial-version', TUTORIAL_VERSION);
    }
    
    // Log tutorial state for debugging
    console.log('[TUTORIAL] Mount state:', {
      hasCompleted: hasCompletedTutorial,
      version: completedVersion || 'none',
      expectedVersion: TUTORIAL_VERSION,
    });
  }, []);

  const tutorialSteps: DriveStep[] = [
    {
      element: '[data-tutorial="welcome"]',
      popover: {
        title: '👋 Welcome to ARIA!',
        description: 'ARIA is your AI-powered business simulation platform. Let me show you how it works with a quick interactive demo!',
        side: 'bottom',
        align: 'center',
      },
    },
    {
      element: '[data-tutorial="chat-panel"]',
      popover: {
        title: '💬 Chat Panel',
        description: 'Describe your business scenario or ask questions here. ARIA analyzes your input and creates realistic customer simulations to predict outcomes.',
        side: 'left',
        align: 'start',
      },
    },
    {
      element: '[data-tutorial="real-world-context"]',
      popover: {
        title: '🌍 Real-World Context',
        description: 'Toggle this ON to incorporate live news, economic data, and Malaysian market conditions into your simulations for more accurate predictions.',
        side: 'left',
        align: 'start',
      },
    },
    {
      element: '[data-tutorial="simulation-settings"]',
      popover: {
        title: '⚙️ Simulation Settings',
        description: 'Configure your target audience here. I\'ve set this to "Fast" mode with 20 agents for a quick demo. You can adjust these settings anytime for your real simulations.',
        side: 'left',
        align: 'start',
      },
    },
    {
      element: '[data-tutorial="history-sidebar"]',
      popover: {
        title: '📚 History Sidebar',
        description: 'All your past simulations are saved here. Click the menu icon (☰) on the top left to open your history anytime and review previous results.',
        side: 'right',
        align: 'start',
      },
    },
    {
      element: '[data-tutorial="demo-scenario-card"]',
      popover: {
        title: '🎯 Click Here to Run Demo',
        description: 'I\'ve prepared a sample scenario: "Price Increase +15%". Click directly on this card to run the simulation and see how ARIA works!',
        side: 'top',
        align: 'center',
        showButtons: [], // Hide all buttons - user must click the card
      },
    },
    {
      element: '[data-tutorial="simulation-running"]',
      popover: {
        title: '🎬 Simulation Started!',
        description: 'Great! The simulation is now running. This dashboard shows the simulation progress and will display the results when complete.',
        side: 'top',
        align: 'center',
      },
    },
    {
      element: '[data-tutorial="monte-carlo-badge"]',
      popover: {
        title: '🔁 Run X of Y - Monte Carlo Method',
        description: 'Seeing “Run 1 of 30”? ARIA runs your scenario multiple times because Large Language Models can produce different results each time. Up to 30 runs are combined to calculate an average outcome, making the results more reliable.',
        side: 'bottom',
        align: 'start',
      },
    },
    {
      element: '[data-tutorial="monte-carlo-badge"]',
      popover: {
        title: '📊 Results Are Stable',
        description: 'This percentage shows how much the results vary between runs. When it falls below 5%, the results are considered consistent. If it is higher, ARIA performs more simulations until the results become more stable.',
        side: 'bottom',
        align: 'start',
      },
    },
    {
      popover: {
        title: '🎉 Tutorial Complete!',
        description: 'You\'ve learned how ARIA works! All your simulations are automatically saved in the history sidebar. Now try running your own scenarios to see how your business decisions would play out.',
        showButtons: ['next'], // Only show next/done button (which becomes "I understand!" on last step)
      },
    },
  ];

  const driverConfig: Config = {
    showProgress: true,
    progressText: '{{current}} of {{total}}',
    nextBtnText: 'Next →',
    doneBtnText: 'Done!',
    showButtons: ['next', 'close'], // No previous button - linear flow only
    allowClose: false, // Prevent closing by clicking outside
    smoothScroll: true,
    animate: true,
    onDestroyed: () => {
      localStorage.setItem(TUTORIAL_STORAGE_KEY, 'true');
      localStorage.setItem('aria-tutorial-version', TUTORIAL_VERSION);
      // Clean up demo flags - always remove scenario when tutorial ends
      localStorage.removeItem(TUTORIAL_DEMO_READY);
      localStorage.removeItem(TUTORIAL_DEMO_SCENARIO);
      window.dispatchEvent(new CustomEvent('tutorial-cleanup'));
    },
    onDeselected: () => {
      // Completely prevent deselection - user must use buttons or X
      return false;
    },
    onPopoverRender: () => {
      // Prevent clicking outside to close
      const overlay = document.querySelector('.driver-overlay');
      if (overlay) {
        (overlay as HTMLElement).style.pointerEvents = 'auto';
      }
    },
    onCloseClick: () => {
      // User clicked X button - clean up demo scenario
      localStorage.removeItem(TUTORIAL_DEMO_READY);
      localStorage.removeItem(TUTORIAL_DEMO_SCENARIO);
      
      // Force ChatPanel to remove scenario
      window.dispatchEvent(new CustomEvent('tutorial-cleanup'));
      
      if (driverRef.current) {
        driverRef.current.destroy();
      }
    },
  };

  const startTutorial = useCallback((forceStart = false) => {
    const hasCompletedTutorial = localStorage.getItem(TUTORIAL_STORAGE_KEY);
    const completedVersion = localStorage.getItem('aria-tutorial-version');
    
    console.log('[TUTORIAL] startTutorial called', {
      forceStart,
      hasCompleted: hasCompletedTutorial,
      version: completedVersion,
      shouldStart: !hasCompletedTutorial || forceStart,
    });
    
    // Force restart if version mismatch
    const needsRestart = hasCompletedTutorial && completedVersion !== TUTORIAL_VERSION;
    
    if (!hasCompletedTutorial || forceStart || needsRestart) {
      console.log('[TUTORIAL] Starting tutorial...', { forceStart, needsRestart });
      
      // Clear any previous demo flags
      localStorage.removeItem(TUTORIAL_DEMO_READY);
      localStorage.removeItem(TUTORIAL_DEMO_SCENARIO);
      
      // Clear old completion flag if version mismatch
      if (needsRestart) {
        localStorage.removeItem(TUTORIAL_STORAGE_KEY);
      }
      
      // Set up demo scenario BEFORE starting so the card appears
      const demoScenario = {
        scenario_name: 'Demo: Price Increase +15%',
        scenario_type: 'price_change',
        description: 'Test how customers react when you raise prices by 15%. This is a common scenario for businesses testing price optimization.',
        parameters: {
          price_change_percent: 15,
        },
        expected_impact: 'Moderate risk - some customers may skip or churn',
      };
      localStorage.setItem(TUTORIAL_DEMO_SCENARIO, JSON.stringify(demoScenario));
      localStorage.setItem(TUTORIAL_DEMO_READY, 'true');
      
      console.log('[TUTORIAL] Demo scenario set in localStorage');
      
      // Trigger ChatPanel to show the demo scenario - multiple times to ensure it's received
      window.dispatchEvent(new CustomEvent('tutorial-demo-ready'));
      
      // Wait longer for ChatPanel to render the demo card
      setTimeout(() => {
        const demoCard = document.querySelector('[data-tutorial="demo-scenario-card"]');
        
        // Trigger again if card appeared
        if (demoCard) {
          window.dispatchEvent(new CustomEvent('tutorial-demo-ready'));
        }
        
        // Wait a moment for the DOM to update with the demo card
      setTimeout(() => {
        // Include ALL steps - even if elements don't exist yet
        // Simulation steps will be skipped if element doesn't exist but will be available later
        const availableSteps = tutorialSteps.filter((step) => {
          if (!step.element) return true; // Non-element steps always included
          if (typeof step.element !== 'string') return true;
          
          // Always include simulation steps - they'll appear during demo
          if (
            step.element === '[data-tutorial="simulation-running"]' ||
            step.element === '[data-tutorial="monte-carlo-badge"]'
          ) {
            return true;
          }
          
          // For other steps, check if element exists
          const element = document.querySelector(step.element);
          return !!element;
        });

      if (driverRef.current) {
        driverRef.current.destroy();
      }

      driverRef.current = driver({
        ...driverConfig,
        steps: availableSteps,
        onHighlightStarted: () => {
          const currentIndex = driverRef.current?.getActiveIndex();
          const currentStep = availableSteps[currentIndex ?? 0];
          
          // If element doesn't exist for this step, skip to next
          if (currentStep?.element && typeof currentStep.element === 'string') {
            const el = document.querySelector(currentStep.element);
            if (!el) {
              // Don't skip automatically - wait for advanceToSimulationStep
              return;
            }
          }
          
          // After step 5 (demo scenario card step), allow clicks everywhere
          if (currentIndex !== undefined && currentIndex >= 5) {
            const overlay = document.querySelector('.driver-overlay');
            if (overlay) {
              overlay.classList.add('tutorial-interactive-phase');
            }
          } else {
            // Before step 6, block clicks
            const overlay = document.querySelector('.driver-overlay');
            if (overlay) {
              overlay.classList.remove('tutorial-interactive-phase');
            }
          }
        },
      });

      driverRef.current.drive();
      console.log('[TUTORIAL] Tutorial started with', availableSteps.length, 'steps');
      }, 500); // Increased delay for demo card to render
      }, 100); // Check after 100ms
    } else {
      console.log('[TUTORIAL] Tutorial already completed, skipping');
    }
  }, []); // Empty deps - function should be stable

  const resetTutorial = useCallback(() => {
    console.log('[TUTORIAL] Resetting tutorial manually');
    localStorage.removeItem(TUTORIAL_STORAGE_KEY);
    localStorage.removeItem('aria-tutorial-version');
    localStorage.removeItem(TUTORIAL_DEMO_READY);
    localStorage.removeItem(TUTORIAL_DEMO_SCENARIO);
    startTutorial(true);
  }, [startTutorial]);

  // Expose reset function globally for easy testing
  useEffect(() => {
    (window as any).resetTutorial = () => {
      console.log('[TUTORIAL] Global reset called');
      localStorage.removeItem(TUTORIAL_STORAGE_KEY);
      localStorage.removeItem('aria-tutorial-version');
      localStorage.removeItem(TUTORIAL_DEMO_READY);
      localStorage.removeItem(TUTORIAL_DEMO_SCENARIO);
      window.location.reload();
    };
    return () => {
      delete (window as any).resetTutorial;
    };
  }, []);

  // Function to advance tutorial to next simulation-related step
  const advanceToSimulationStep = useCallback((stepType: 'running' | 'monte-carlo' | 'convergence' | 'results') => {
    if (!driverRef.current) {
      return;
    }
    
    const currentStep = driverRef.current.getActiveIndex();
    if (currentStep === undefined) {
      return;
    }

    // Only advance if we're past the demo scenario step (step 5)
    // This prevents glitching back to start
    if (currentStep < 5) {
      return;
    }

    // Find the appropriate step by matching element or title
    const steps = driverRef.current.getConfig().steps || [];
    let targetIndex = -1;

    switch (stepType) {
      case 'running':
        // Find "Simulation Started" step (simulation-running element)
        targetIndex = steps.findIndex(s => 
          s.element === '[data-tutorial="simulation-running"]' ||
          s.popover?.title?.includes('Simulation Started')
        );
        break;
      case 'monte-carlo':
        // Find "Run X of Y" step (second monte-carlo badge step)
        targetIndex = steps.findIndex(s => 
          s.popover?.title?.includes('Run X of Y')
        );
        break;
      case 'convergence':
        // Find "Results Are Stable" step (third monte-carlo badge step)
        targetIndex = steps.findIndex(s => 
          s.popover?.title?.includes('Results Are Stable')
        );
        break;
      case 'results':
        // Results step removed - just move to final step
        targetIndex = steps.length - 1; // Go to tutorial complete
        break;
    }
    
    if (targetIndex > currentStep) {
      // Auto-advance to the target step with a small delay
      setTimeout(() => {
        if (driverRef.current) {
          driverRef.current.moveTo(targetIndex);
        }
      }, 300);
    }
  }, []); // Stable function

  useEffect(() => {
    // Listen for simulation stop/cancel during tutorial
    const handleSimulationStop = () => {
      const isDemoActive = !!localStorage.getItem(TUTORIAL_DEMO_READY);
      const isTutorialActive = driverRef.current && driverRef.current.isActive();
      
      if (isDemoActive && isTutorialActive) {
        console.log('[TUTORIAL] Simulation stopped during tutorial - canceling tutorial');
        // Clean up and destroy tutorial
        localStorage.removeItem(TUTORIAL_DEMO_READY);
        localStorage.removeItem(TUTORIAL_DEMO_SCENARIO);
        window.dispatchEvent(new CustomEvent('tutorial-cleanup'));
        
        if (driverRef.current) {
          driverRef.current.destroy();
        }
      }
    };
    
    // Listen for demo scenario click - advance to next step
    const handleDemoClicked = () => {
      if (driverRef.current && driverRef.current.isActive()) {
        // Move to next step
        driverRef.current.moveNext();
      }
    };
    
    window.addEventListener('simulation-stopped', handleSimulationStop);
    window.addEventListener('simulation-cancelled', handleSimulationStop);
    window.addEventListener('tutorial-demo-clicked', handleDemoClicked);
    
    return () => {
      window.removeEventListener('simulation-stopped', handleSimulationStop);
      window.removeEventListener('simulation-cancelled', handleSimulationStop);
      window.removeEventListener('tutorial-demo-clicked', handleDemoClicked);
      
      if (driverRef.current) {
        driverRef.current.destroy();
      }
    };
  }, []);

  return {
    startTutorial,
    resetTutorial,
    advanceToSimulationStep,
  };
};
