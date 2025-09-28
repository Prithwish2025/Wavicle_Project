document.addEventListener("DOMContentLoaded", function() {
  // Mark all present checkbox handler
  const markAllBtn = document.getElementById("markAllPresent");
  if(markAllBtn) {
    markAllBtn.addEventListener("click", function() {
      document.querySelectorAll("input[type=checkbox]").forEach(cb => cb.checked = true);
    });
  }

  // Confirmation before submitting attendance
  const attendanceForm = document.getElementById("attendanceForm");
  if(attendanceForm){
    attendanceForm.addEventListener("submit", function(e){
      if(!confirm("Are you sure you want to save attendance?")) {
        e.preventDefault();
      }
    });
  }

  // Deadline countdown (assignments)
  document.querySelectorAll("[data-duedate]").forEach(el=>{
    const due = new Date(el.dataset.duedate);
    const diff = due - new Date();
    if(diff>0){
      const daysLeft = Math.ceil(diff/(1000*60*60*24));
      el.innerText = daysLeft+" days left";
    }
  });

  // Meeting countdown
  document.querySelectorAll("[data-meetingtime]").forEach(el=>{
    const mt = new Date(el.dataset.meetingtime);
    const diff = mt - new Date();
    if(diff>0 && diff < 24*60*60*1000){
      const hrsLeft = Math.floor(diff/(1000*60*60));
      el.innerText = "Starts in "+hrsLeft+"h";
      el.style.color = "red";
    }
  });
});
