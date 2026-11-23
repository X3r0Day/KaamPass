import { test, expect, type Page } from "@playwright/test";
import { randomInt } from "node:crypto";

const baseURL = "http://127.0.0.1:3000";
const emulator = "http://127.0.0.1:19099/emulator/v1/projects/demo-kaampaas";
const area = "201204-patla";

async function signIn(page:Page, role:string, phone:string) {
  await page.goto(`${baseURL}/login?role=${role}`);
  await page.getByLabel("Mobile number").fill(phone);
  await page.getByRole("checkbox").check();
  await page.getByRole("button",{name:"Send SMS code"}).click();
  await page.getByLabel("Six-digit code").waitFor();
  const {verificationCodes} = await (await page.request.get(`${emulator}/verificationCodes`)).json();
  const row = verificationCodes.filter((r:{phoneNumber:string})=>r.phoneNumber===phone).at(-1);
  expect(row).toBeTruthy();
  await page.getByLabel("Six-digit code").fill(row.code);
  await page.getByRole("button",{name:"Verify code"}).click();
}

async function enroll(page:Page,role:"worker"|"employer",name:string,phone:string) {
  await signIn(page,role,phone);
  await page.getByLabel("Your name or business name").fill(name);
  await page.getByRole("combobox",{name:/Work area/}).selectOption(area);
  if(role==="worker"){
    await page.getByLabel("Mason",{exact:true}).check();
    await page.getByLabel("Short-term work",{exact:true}).check();
  }
  await page.getByRole("button",{name:"Review details"}).click();
  await page.getByRole("button",{name:"Confirm profile"}).click();
  await expect(page).toHaveURL(`${baseURL}/dashboard`);
  await expect(page.locator(".workspace").getByRole("heading",{name,exact:true})).toBeVisible();
  return (await page.locator(".subhead").innerText()).split("/")[1].trim();
}

async function post(page:Page,description:string,permanent=false) {
  await page.getByRole("button",{name:"Post a job",exact:true}).click();
  await page.getByRole("combobox",{name:/^Trade/}).selectOption("mason");
  if(permanent)await page.getByRole("combobox",{name:/Opening type/}).selectOption("permanent");
  await page.getByLabel("Offered pay (₹)").fill(permanent?"18000":"750");
  await page.getByLabel("Work details (optional)").fill(description);
  await page.getByRole("button",{name:"Review details"}).click();
  await page.getByLabel(/Share my phone number/).check();
  await page.getByRole("button",{name:"Publish opening"}).click();
  await expect(page.getByRole("article").filter({hasText:description})).toBeVisible();
}

test("two phone accounts hire for a shift and a permanent opening",async({browser})=>{
  const workerContext=await browser.newContext({viewport:{width:360,height:780}}),ownerContext=await browser.newContext();
  const worker=await workerContext.newPage(),owner=await ownerContext.newPage();
  const n=randomInt(1000000,8999999),workerPhone=`+1555${n}`,employerPhone=`+1555${n+1}`;
  const shift=`Shift ${n}`,permanent=`Shop hire ${n}`;
  owner.on("dialog",async d=>d.accept());
  try{
    const id=await enroll(worker,"worker",`Worker ${n}`,workerPhone);
    await worker.getByRole("button",{name:"Open to hirers",exact:true}).click();
    await expect(worker.getByRole("heading",{name:"Open to hirers"})).toBeVisible();
    await enroll(owner,"employer",`Shop ${n}`,employerPhone);
    await post(owner,shift);
    const listing=owner.getByRole("article").filter({hasText:shift});
    await listing.getByRole("button",{name:"Available workers"}).click();
    const person=listing.locator(".spread").filter({hasText:id});
    await person.getByRole("button",{name:"Invite",exact:true}).click();
    await expect(person.getByRole("button",{name:"Invited"})).toBeDisabled();
    await worker.getByRole("button",{name:"Invitations",exact:true}).click();
    const offer=worker.getByRole("article").filter({hasText:shift});
    await offer.getByLabel(/Share my phone number/).check();
    await offer.getByRole("button",{name:"Accept invitation"}).click();
    await expect(offer.getByText("Interest sent")).toBeVisible();
    await listing.getByRole("button",{name:"Interested workers"}).click();
    await person.getByRole("button",{name:"Assign worker"}).click();
    await listing.getByRole("button",{name:"See contact details"}).click();
    await expect(listing.getByRole("link",{name:new RegExp(`Worker ${n}`)})).toHaveAttribute("href",`tel:${workerPhone}`);
    await listing.getByRole("button",{name:"Mark work complete"}).click();
    await expect(listing.getByRole("button",{name:"See contact details"})).toHaveCount(0);
    await worker.getByRole("button",{name:"My applications"}).click();
    await offer.getByLabel("Amount received (₹)").fill("725");
    await offer.getByRole("button",{name:"Save changes"}).click();
    await expect(worker.locator(".stats")).toContainText("₹725");

    await post(owner,permanent,true);
    await worker.getByRole("button",{name:"Nearby jobs"}).click();
    await expect(worker.getByRole("article").filter({hasText:permanent})).toHaveCount(0);
    await worker.getByRole("link",{name:"Edit profile"}).first().click();
    await worker.getByLabel("Permanent job",{exact:true}).check();
    await worker.getByRole("button",{name:"Review details"}).click();await worker.getByRole("button",{name:"Save changes"}).click();
    await worker.getByRole("button",{name:"Pause discovery"}).click();
    await expect(worker.getByRole("heading",{name:"Paused"})).toBeVisible();
    const vacancy=owner.getByRole("article").filter({hasText:permanent});
    await vacancy.getByRole("button",{name:"Available workers"}).click();
    await expect(vacancy.locator(".review h3")).toHaveText("Available workers");
    await expect(vacancy.getByText(id,{exact:false})).toHaveCount(0);
    const match=worker.getByRole("article").filter({hasText:permanent});
    await match.getByLabel(/Share my phone number/).check();await match.getByRole("button",{name:"Express interest"}).click();
    await vacancy.getByRole("button",{name:"Interested workers"}).click();
    await vacancy.locator(".spread").filter({hasText:id}).getByRole("button",{name:"Assign worker"}).click();
    await vacancy.getByRole("button",{name:"Confirm permanent hire"}).click();
    await expect(vacancy.locator(".tag").last()).toHaveText("Permanent placements");
    await worker.getByRole("button",{name:"Sign out of all devices"}).click();
    await expect(worker).toHaveURL(`${baseURL}/`);
    await signIn(worker,"worker",workerPhone);
    await expect(worker.locator(".subhead")).toContainText(id);
    await expect(worker.locator(".stats")).toContainText("₹725");
  }finally{await workerContext.close();await ownerContext.close();}
});

test("Hindi on a shared screen fits 360px and mic denial preserves the draft",async({page,context})=>{
  await page.setViewportSize({width:360,height:780});
  await page.goto(baseURL);
  await expect(page.getByRole("link", { name: "WhatsApp (temporarily unavailable)" })).toHaveAttribute("aria-disabled", "true");
  await expect(page.locator('a[href^="https://wa.me/"]')).toHaveCount(0);
  await page.getByRole("button",{name:"हिन्दी"}).click();
  await expect(page.locator(".placeTag")).toContainText("गाज़ियाबाद");
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.getByRole("button",{name:"English"}).click();
  await signIn(page,"worker",`+1555${randomInt(1000000,8999999)}`);
  await page.getByLabel("Your name or business name").fill("Shared browser check");
  await context.clearPermissions();
  await page.evaluate(()=>{navigator.mediaDevices.getUserMedia=async()=>{throw new DOMException("Denied","NotAllowedError");};});
  await page.getByRole("button",{name:"Start recording"}).click();
  await expect(page.locator("main").getByRole("alert")).toContainText("Microphone unavailable");
  await expect(page.getByLabel("Your name or business name")).toHaveValue("Shared browser check");
});
